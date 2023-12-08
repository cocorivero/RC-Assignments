import argparse
from copy import deepcopy
from enum import Enum, auto
import random
import sys
import time

from binascii import crc32

class Msg:
    MSG_SIZE = 20

    def __init__(self, data):
        self.data = data                

    def __str__(self):
        return 'Msg(data=%s)' % (self.data)


class Pkt:
    def __init__(self, seqnum, acknum, checksum, payload):
        self.seqnum = seqnum            
        self.acknum = acknum          
        self.checksum = checksum     
        self.payload = payload        

    def __str__(self):
        return ('Pkt(seqnum=%s, acknum=%s, checksum=%s, payload=%s)'
                % (self.seqnum, self.acknum, self.checksum, self.payload))


class EntityA:

    def __init__(self, seqnum_limit):
        # How long to wait for ack?
        self.WAIT_TIME = 10.0 + 4.0 * seqnum_limit//2

        # Configuration.
        self.seqnum_limit = seqnum_limit
        self.window_size = seqnum_limit//2

        # State.
        self.base = 0
        self.layer3_pkts = []
        self.layer5_msgs = []
        self.made_progress = True
        self.n_no_progress = 0

    def output(self, message):
        self.layer5_msgs.append(message)
        self.maybe_output_from_queue()

    def maybe_output_from_queue(self):
        while (self.layer5_msgs
               and len(self.layer3_pkts) < self.window_size):
            m = self.layer5_msgs.pop(0)
            s = self.next_seqnum()
            p = Pkt(s, 0, 0, m.data)
            pkt_insert_checksum(p)
            self.layer3_pkts.append(p)
            to_layer3(self, p)
            # print(f'[A:base {self.base}] Sending {p}')
            if len(self.layer3_pkts) == 1:
                start_timer(self, self.WAIT_TIME)

    def next_seqnum(self):
        return (self.base + len(self.layer3_pkts)) % self.seqnum_limit

    def input(self, packet):
        if pkt_is_corrupt(packet):
            return

        # print(f'[A:base {self.base}] Received ack for packet {packet.acknum}.')
        i = 0
        while i < len(self.layer3_pkts):
            if self.layer3_pkts[i].seqnum != packet.acknum:
                i += 1
                continue

            # All the packets up to and including i are ack'ed.
            self.base += i+1
            self.layer3_pkts = self.layer3_pkts[i+1:]
            if TRACE>0:
                if (self.n_no_progress > 0
                    and not self.made_progress):
                    print(f'[A:base {self.base}] Finally made some progress!')
            self.made_progress = True
            self.n_no_progress = 0
            stop_timer(self)
            if self.layer3_pkts:
                start_timer(self, self.WAIT_TIME)
            self.maybe_output_from_queue()
            break

    def timer_interrupt(self):
        if not self.made_progress:
            self.n_no_progress += 1
            if TRACE>0:
                print(f'[A:base {self.base}] Rats!  Made no progress for {self.n_no_progress} timeouts.')
        self.made_progress = False
        # print(f'[A:base {self.base}] Resending {len(self.layer3_pkts)} packets.')
        for p in self.layer3_pkts:
            to_layer3(self, p)
        start_timer(self, self.WAIT_TIME * (self.n_no_progress+1))

class EntityB:
    def __init__(self, seqnum_limit):
        # Configuration.
        self.seqnum_limit = seqnum_limit

        # State.
        self.expected_seqnum = 0
        self.last_acked = seqnum_limit-1

    def input(self, packet):
        if (pkt_is_corrupt(packet)
            or packet.seqnum != self.expected_seqnum):
            p = Pkt(0, self.last_acked, 0, packet.payload)
            pkt_insert_checksum(p)
            to_layer3(self, p)
        else:
            to_layer5(self, Msg(packet.payload))
            p = Pkt(0, self.expected_seqnum, 0, packet.payload)
            pkt_insert_checksum(p)
            to_layer3(self, p)
            self.last_acked = self.expected_seqnum
            self.expected_seqnum = self.next_expected_seqnum()

    def next_expected_seqnum(self):
        return (self.expected_seqnum + 1) % self.seqnum_limit

    def timer_interrupt(self):
        pass

def pkt_compute_checksum(packet):
    crc = 0
    crc = crc32(packet.seqnum.to_bytes(4, byteorder='big'), crc)
    crc = crc32(packet.acknum.to_bytes(4, byteorder='big'), crc)
    crc = crc32(packet.payload, crc)
    return crc

def pkt_insert_checksum(packet):
    packet.checksum = pkt_compute_checksum(packet)

def pkt_is_corrupt(packet):
    return pkt_compute_checksum(packet) != packet.checksum

def start_timer(calling_entity, increment):
    the_sim.start_timer(calling_entity, increment)

def stop_timer(calling_entity):
    the_sim.stop_timer(calling_entity)

def to_layer3(calling_entity, packet):
    the_sim.to_layer3(calling_entity, packet)

def to_layer5(calling_entity, message):
    the_sim.to_layer5(calling_entity, message)

def get_time(calling_entity):
    return the_sim.get_time(calling_entity)

class EventType(Enum):
    TIMER_INTERRUPT = auto()
    FROM_LAYER5 = auto()
    FROM_LAYER3 = auto()

class Event:
    def __init__(self, ev_time, ev_type, ev_entity, packet=None):
        self.ev_time = ev_time      # float
        self.ev_type = ev_type      # EventType
        self.ev_entity = ev_entity  # EntityA or EntityB
        self.packet = packet        # Pkt or None

class Simulator:
    def __init__(self, options, cbA=None, cbB=None):
        self.n_sim                = 0
        self.n_sim_max            = options.num_msgs
        self.time                 = 0.000
        self.interarrival_time    = options.interarrival_time
        self.loss_prob            = options.loss_prob
        self.corrupt_prob         = options.corrupt_prob
        self.seqnum_limit         = options.seqnum_limit
        self.n_to_layer3_A        = 0
        self.n_to_layer3_B        = 0
        self.n_lost               = 0
        self.n_corrupt            = 0
        self.n_to_layer5_A        = 0
        self.n_to_layer5_B        = 0

        if options.random_seed is None:
            self.random_seed      = time.time_ns()
        else:
            self.random_seed      = options.random_seed
        random.seed(self.random_seed)

        if self.seqnum_limit < 2:
            self.seqnum_limit_n_bits = 0
        else:
            # How many bits to represent integers in [0, seqnum_limit-1]?
            self.seqnum_limit_n_bits = (self.seqnum_limit-1).bit_length()

        self.trace                = options.trace
        self.to_layer5_callback_A = cbA
        self.to_layer5_callback_B = cbB

        self.entity_A             = EntityA(self.seqnum_limit)
        self.entity_B             = EntityB(self.seqnum_limit)
        self.event_list           = []

    def get_stats(self):
        stats = {'n_sim'             : self.n_sim,
                 'n_sim_max'         : self.n_sim_max,
                 'time'              : self.time,
                 'interarrival_time' : self.interarrival_time,
                 'loss_prob'         : self.loss_prob,
                 'corrupt_prob'      : self.corrupt_prob,
                 'seqnum_limit'      : self.seqnum_limit,
                 'random_seed'       : self.random_seed,
                 'n_to_layer3_A'     : self.n_to_layer3_A,
                 'n_to_layer3_B'     : self.n_to_layer3_B,
                 'n_lost'            : self.n_lost,
                 'n_corrupt'         : self.n_corrupt,
                 'n_to_layer5_A'     : self.n_to_layer5_A,
                 'n_to_layer5_B'     : self.n_to_layer5_B
        }
        return stats

    def run(self):
        if self.trace>0:
            print('\n===== SIMULATION BEGINS')

        self._generate_next_arrival()

        while (self.event_list
               and self.n_sim < self.n_sim_max):
            ev = self.event_list.pop(0)
            if self.trace>2:
                print(f'\nEVENT time: {ev.ev_time}, ', end='')
                if ev.ev_type == EventType.TIMER_INTERRUPT:
                    print(f'timer_interrupt, ', end='')
                elif ev.ev_type == EventType.FROM_LAYER5:
                    print(f'from_layer5, ', end='')
                elif ev.ev_type == EventType.FROM_LAYER3:
                    print(f'from_layer3, ', end='')
                else:
                    print(f'unknown_type, ', end='')
                print(f'entity: {ev.ev_entity}')

            self.time = ev.ev_time

            if ev.ev_type == EventType.FROM_LAYER5:
                self._generate_next_arrival()
                j = self.n_sim % 26
                m = bytes([97+j for i in range(Msg.MSG_SIZE)])
                if self.trace>2:
                    print(f'          MAINLOOP: data given to student: {m}')
                self.n_sim += 1
                ev.ev_entity.output(Msg(m))

            elif ev.ev_type == EventType.FROM_LAYER3:
                ev.ev_entity.input(deepcopy(ev.packet))

            elif ev.ev_type == EventType.TIMER_INTERRUPT:
                ev.ev_entity.timer_interrupt()

            else:
                print('INTERNAL ERROR: unknown event type; event ignored.')

        if self.trace>0:
            print('===== SIMULATION ENDS')

    def _insert_event(self, event):
        if self.trace>2:
            print(f'            INSERTEVENT: time is {self.time}')
            print(f'            INSERTEVENT: future time will be {event.ev_time}')
        # Python 3.10+: use the bisect module:
        # insort(self.event_list, event, key=lambda e: e.ev_time)
        i = 0
        while (i < len(self.event_list)
               and self.event_list[i].ev_time < event.ev_time):
            i += 1
        self.event_list.insert(i, event)

    def _generate_next_arrival(self):
        if self.trace>2:
            print('          GENERATE NEXT ARRIVAL: creating new arrival')

        x = self.interarrival_time * 2.0 * random.random()
        ev = Event(self.time+x, EventType.FROM_LAYER5, self.entity_A)
        self._insert_event(ev)

    def _valid_entity(self, e, method_name):
        if (e is self.entity_A
            or e is self.entity_B):
            return True
        print(f'''WARNING: entity in call to `{method_name}` is invalid!
  Invalid entity: {e}
  Call ignored.''')
        return False

    def _valid_increment(self, i, method_name):
        if ((type(i) is int or type(i) is float)
            and i >= 0.0):
            return True
        print(f'''WARNING: increment in call to `{method_name}` is invalid!
  Invalid increment: {i}
  Call ignored.''')
        return False

    def _valid_message(self, m, method_name):
        if (type(m) is Msg
            and type(m.data) is bytes
            and len(m.data) == Msg.MSG_SIZE):
            return True
        print(f'''WARNING: message in call to `{method_name}` is invalid!
  Invalid message: {m}
  Call ignored.''')
        return False

    def _valid_packet(self, p, method_name):
        if (type(p) is Pkt
            and type(p.seqnum) is int
            and 0 <= p.seqnum < self.seqnum_limit
            and type(p.acknum) is int
            and 0 <= p.acknum < self.seqnum_limit
            and type(p.checksum) is int
            and type(p.payload) is bytes
            and len(p.payload) == Msg.MSG_SIZE):
            return True
        # Issue special warnings for invalid seqnums and acknums.
        if (type(p.seqnum) is int
            and not (0 <= p.seqnum < self.seqnum_limit)):
            print(f'''WARNING: seqnum in call to `{method_name}` is invalid!
  Invalid packet: {p}
  Call ignored.''')
        elif (type(p.acknum) is int
              and not (0 <= p.acknum < self.seqnum_limit)):
            print(f'''WARNING: acknum in call to `{method_name}` is invalid!
  Invalid packet: {p}
  Call ignored.''')
        else:
            print(f'''WARNING: packet in call to `{method_name}` is invalid!
  Invalid packet: {p}
  Call ignored.''')
        return False

    def start_timer(self, entity, increment):
        if not self._valid_entity(entity, 'start_timer'):
            return
        if not self._valid_increment(increment, 'start_timer'):
            return

        if self.trace>2:
            print(f'          START TIMER: starting timer at {self.time}')

        for e in self.event_list:
            if (e.ev_type == EventType.TIMER_INTERRUPT
                and e.ev_entity is entity):
                print('WARNING: attempt to start a timer that is already started!')
                return

        ev = Event(self.time+increment, EventType.TIMER_INTERRUPT, entity)
        self._insert_event(ev)

    def stop_timer(self, entity):
        if not self._valid_entity(entity, 'stop_timer'):
            return

        if self.trace>2:
            print(f'          STOP TIMER: stopping timer at {self.time}')

        i = 0
        while i < len(self.event_list):
            if (self.event_list[i].ev_type == EventType.TIMER_INTERRUPT
                and self.event_list[i].ev_entity is entity):
                break
            i += 1
        if i < len(self.event_list):
            self.event_list.pop(i)
        else:
            print('WARNING: unable to stop timer; it was not running.')

    def to_layer3(self, entity, packet):
        if not self._valid_entity(entity, 'to_layer3'):
            return
        if not self._valid_packet(packet, 'to_layer3'):
            return

        if entity is self.entity_A:
            receiver = self.entity_B
            self.n_to_layer3_A += 1
        else:
            receiver = self.entity_A
            self.n_to_layer3_B += 1

        # Simulate losses.
        if random.random() < self.loss_prob:
            self.n_lost += 1
            if self.trace>0:
                print('          TO_LAYER3: packet being lost')
            return

        seqnum = packet.seqnum
        acknum = packet.acknum
        checksum = packet.checksum
        payload = packet.payload

        # Simulate corruption.
        if random.random() < self.corrupt_prob:
            self.n_corrupt += 1
            x = random.random()
            if (x < 0.75
                or self.seqnum_limit_n_bits == 0):
                payload = b'Z' + payload[1:]
            elif x < 0.875:
                # Flip a random bit in the seqnum.
                # The result might be greater than seqnum_limit if seqnum_limit
                # is not a power of two.  This is OK.
                # Recall that randrange(x) returns an int in [0, x).
                seqnum ^= 2**random.randrange(self.seqnum_limit_n_bits)
                # Kurose's simulator simply did:
                # seqnum = 999999
            else:
                # Flip a random bit in the acknum.
                acknum ^= 2**random.randrange(self.seqnum_limit_n_bits)
                # Kurose's simulator simply did:
                # acknum = 999999
            if self.trace>0:
                print('          TO_LAYER3: packet being corrupted')

        last_time = self.time
        for e in self.event_list:
            if (e.ev_type == EventType.FROM_LAYER3
                and e.ev_entity is receiver):
                last_time = e.ev_time
        arrival_time = last_time + 1.0 + 8.0*random.random()

        p = Pkt(seqnum, acknum, checksum, payload)
        ev = Event(arrival_time, EventType.FROM_LAYER3, receiver, p)
        if self.trace>2:
            print('          TO_LAYER3: scheduling arrival on other side')
        self._insert_event(ev)

    def to_layer5(self, entity, message):
        if not self._valid_entity(entity, 'to_layer5'):
            return
        if not self._valid_message(message, 'to_layer5'):
            return

        if entity is self.entity_A:
            self.n_to_layer5_A += 1
            callback = self.to_layer5_callback_A
        else:
            self.n_to_layer5_B += 1
            callback = self.to_layer5_callback_B

        if self.trace>2:
            print(f'          TO_LAYER5: data received: {message.data}')
        if callback:
            callback(message.data)

    def get_time(self, entity):
        if not self._valid_entity(entity, 'get_time'):
            return
        return self.time

TRACE = 0

the_sim = None

def report_config():
    # Obtener estadísticas de la simulación
    stats = the_sim.get_stats()
    
    # Imprimir configuración de la simulación
    print(f'''CONFIGURACIÓN DE LA SIMULACIÓN
--------------------------------------
(-n) # mensajes de la capa 5 a proporcionar:{stats['n_sim_max']}
(-d) tiempo promedio entre mensajes de la capa 5:{stats['interarrival_time']}
(-z) límite de seqnum para el protocolo de transporte de datos:{stats['seqnum_limit']}
(-l) probabilidad de pérdida de paquetes de la capa 3:{stats['loss_prob']}
(-c) probabilidad de corrupción de paquetes de la capa 3:{stats['corrupt_prob']}
(-s) semilla aleatoria de la simulación:{stats['random_seed']}
--------------------------------------''')

def report_results():
    # Obtener estadísticas de la simulación
    stats = the_sim.get_stats()
    
    time = stats['time']
    
    # Calcular la tasa de entrega de mensajes de la capa 5 por B en función del tiempo transcurrido
    if time > 0.0:
        tput = stats['n_to_layer5_B'] / time
    else:
        tput = 0.0
    
    # Imprimir resumen de la simulación
    print(f'''\nRESUMEN DE LA SIMULACIÓN
--------------------------------
# mensajes de la capa 5 proporcionados a A:{stats['n_sim']}
# tiempo transcurrido:{time}

# paquetes de la capa 3 enviados por A:{stats['n_to_layer3_A']}
# paquetes de la capa 3 enviados por B:{stats['n_to_layer3_B']}
# paquetes de la capa 3 perdidos:{stats['n_lost']}
# paquetes de la capa 3 corrompidos:{stats['n_corrupt']}
# mensajes de la capa 5 entregados por A:{stats['n_to_layer5_A']}
# mensajes de la capa 5 entregados por B:{stats['n_to_layer5_B']}
# mensajes de la capa 5 por B/tiempo transcurrido:{tput}
--------------------------------''')

def main(options, cb_A=None, cb_B=None):
    global TRACE
    TRACE = options.trace
    
    global the_sim
    the_sim = Simulator(options, cb_A, cb_B)
    
    # Generar informe de configuración
    report_config()
    
    # Ejecutar la simulación
    the_sim.run()

if __name__ == '__main__':
    desc = 'Ejecutar una simulación de un protocolo de transporte de datos confiable.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('-n', type=int, default=10,
                        dest='num_msgs',
                        help=('número de mensajes a simular'
                              ' [int, por defecto: %(default)s]'))
    parser.add_argument('-d', type=float, default=100.0,
                        dest='interarrival_time',
                        help=('tiempo promedio entre mensajes'
                              ' [float, por defecto: %(default)s]'))
    parser.add_argument('-z', type=int, default=16,
                        dest='seqnum_limit',
                        help=('límite de seqnum para el protocolo de transporte de datos; '
                              'todos los seqnums de los paquetes deben ser >=0 y <límite'
                              ' [int, por defecto: %(default)s]'))
    parser.add_argument('-l', type=float, default=0.0,
                        dest='loss_prob',
                        help=('probabilidad de pérdida de paquetes'
                              ' [float, por defecto: %(default)s]'))
    parser.add_argument('-c', type=float, default=0.0,
                        dest='corrupt_prob',
                        help=('probabilidad de corrupción de paquetes'
                              ' [float, por defecto: %(default)s]'))
    parser.add_argument('-s', type=int,
                        dest='random_seed',
                        help=('semilla para el generador de números aleatorios'
                              ' [int, por defecto: %(default)s]'))
    parser.add_argument('-v', type=int, default=0,
                        dest='trace',
                        help=('nivel de seguimiento de eventos'
                              ' [int, por defecto: %(default)s]'))
    options = parser.parse_args()

    # Iniciar la simulación
    main(options)
    
    # Generar informe de resultados
    report_results()
    
    # Salir del programa
    sys.exit(0)
