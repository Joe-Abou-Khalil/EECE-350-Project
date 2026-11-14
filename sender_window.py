"""
sender_window.py — EECE 350 Final Project: Reliable File Transfer over UDP

 MEMBER 2: Kassem Haidar
 Part: Sender — sliding window, TCP-style timer, retransmission, statistics
  DISPLAY NOTE: output formatting in this file was switched to the shared
 display.py helpers (Member 1) so sender, channel and receiver logs share one
"""


import socket  # gives access to the OS's netoworking
import struct  # allows us to convert from numberts to bytes
import time  # gives us the time, timers, ability to pause.


HEADER_FMT = "!BIH"  # format string for packet header used by struct library
# ! = network byte order, B unsigned char for byte type, I unsigned int for seq number,H unsigned short for data length
HEADER_SIZE = struct.calcsize(HEADER_FMT)
TYPE_DATA, TYPE_ACK, TYPE_END = 0, 1, 2

# Packet states inside the window (made them global variables to not run into
# misstyping issues )
NOT_SENT, SENT, ACKED, RETRANSMITTED = "NOT_SENT", "SENT", "ACKED", "RETRANSMITTED"

# Timer parameters
ALPHA = 0.125
BETA = 0.25
INITIAL_TIMEOUT = 1.0  # deafult from book
DUP_ACK_THRESHOLD = 3  # deafult

# colors for terminal
C = {"reset": "\033[0m", "green": "\033[92m", "yellow": "\033[93m",
     "red": "\033[91m", "cyan": "\033[96m", "magenta": "\033[95m",
     "grey": "\033[90m", "bold": "\033[1m"}


class SenderWindow:
    """sliding-window sender by Kassem Haidar"""

    def __init__(self, packets, sock, channel_send, window_size,
                 initial_timeout=INITIAL_TIMEOUT, color=True):
        # inputs and parametrs
        self.packets = packets              # list of packets
        self.total = len(packets)
        # to get acks (send is on unreliable channel)
        self.sock = sock
        self.channel_send = channel_send    # unreliable channel
        self.N = window_size
        self.color = color

        # window stuff
        self.base = 0                       # oldest unacked packet
        self.next_seq = 0                   # next packet to that has not been sent yet
        self.state = [NOT_SENT] * self.total
        # RTT sampling like the book: only ONE packet is timed at a time
        self.timed_seq = None               # seq of the packet being timed
        self.timed_start = 0.0              # when it was sent

        # number of consequitive duplicate acks
        self.dup_count = 0

        # timing stuff
        self.estimated_rtt = None  # estimate of rtt
        self.dev_rtt = None  # estimate of std divitation of rtt
        # the inital timeout, set to 1sec by deafult
        self.initial_timeout = initial_timeout
        # the current timeout interval, initaly set to inital_timeout
        self.timeout_interval = initial_timeout
        self.timer_start = None  # when the current time started. none if not going

        # stuff kept track of for stats. each one enumerated by one when the event happens
        self.stats = {"transmissions": 0, "new_packets": 0, "retransmissions": 0,
                      "timeouts": 0, "fast_retransmits": 0, "acks_received": 0,
                      "duplicate_acks": 0, "transfer_time": 0.0}
        # transfer time is the total time taken to transfer the entire file set once and is not a count

        self.done = False  # becomes true when transfering the file finishes
        # last window printed, make sures the same window isint printed twice
        self._last_window_view = None

    # display stuff

    def _c(self, name, text):
        """colors text"""
        return f"{C[name]}{text}{C['reset']}" if self.color else text  # prints the text normaly if color is off

    def log(self, text, color="reset"):
        """prints the line per event"""
        stamp = time.strftime("%H:%M:%S")  # time
        print(f"{self._c('grey', stamp)}  {self._c(color, text)}",
              flush=True)  # print

    def _seq_label(self, seq):
        """checks in the current sequence is the end packet"""
        return "END" if seq == self.total - 1 else str(seq)

    def show_window(self):
        """prints the packets and whats happining as it happens.
        S = sent, R = retransmitted, A = acknowledged, . = not sent yet."""
        hi = min(self.base + self.N, self.total) - 1
        # returns the window of the packet, checking edge case
        cells = []  # stores what i need to print
        for s in range(self.base, hi+1):  # goes over all the packets to make their strings
            st = self.state[s]  # read the state of that packet (by index)
            label = f"{s}"  # convert to string
            # concider each case and give it a diffrent collor
            if st == SENT:
                cells.append(self._c("yellow", f"{label}:S"))
            elif st == RETRANSMITTED:
                cells.append(self._c("magenta", f"{label}:R"))
            elif st == ACKED:
                cells.append(self._c("green", f"{label}:A"))
            else:  # not yet sent, window just slid
                cells.append(self._c("grey", f"{label}:."))
        view = (f"WINDOW [{self.base}–{max(hi, self.base)}]  "  # max to ensure no reverse windows
                + " ".join(cells)
                # prints timer
                + self._c("grey", f"   timeout={self.timeout_interval*1000:.0f}ms"))
        if view != self._last_window_view:      # print only when something changed
            self._last_window_view = view
            self.log(view, "cyan")  # cyan for the prefix is applied here

    # sending helpers

    def _transmit(self, seq, retransmission=False):
        """Hand a packet to the unreliable channel """
        self.stats["transmissions"] += 1  # updates the stat
        if retransmission:  # handles retransmision case
            self.state[seq] = RETRANSMITTED  # set state to retransmited
            self.stats["retransmissions"] += 1  # update stat
            # we dont take the RTT for a retransmited packet as 2 versions could be in flight and its not clear which is wich.
            if seq == self.timed_seq:
                self.timed_seq = None
        # printing the retransmited packet is handled by the caller of this function
        # (reason of this function call is unkown so we cant handle it)
        else:  # handles normal transmision case
            self.state[seq] = SENT  # set state
            self.stats["new_packets"] += 1  # update stat
            # start timer if not running (for RTT estimation not retransmission)
            if self.timed_seq is None:
                self.timed_seq = seq  # store seq number of the packet being timed
                self.timed_start = time.time()  # store send time to compare later
            self.log(f"SEND {self._seq_label(seq)}", "reset")  # print it
        # gives the unreliable connection the packet
        self.channel_send(self.packets[seq])

    def _computed_timeout(self):
        """computes timeoutInterval = estimatedRTT + 4*devRTT """
        if self.estimated_rtt is None:  # no rtt measured yet, deafult to inital/ 1sec
            return self.initial_timeout
        return self.estimated_rtt + 4 * self.dev_rtt  # else return the normal formula

    def _start_timer(self, after_timeout=False):
        """handles restarting/starting the timer depending on the case. if 
           after timeout is true, then it doubles to avoid congestion and keep system stable
           if not after a timeout it computes the new timeout using the normal helper function.
        """
        if after_timeout:
            self.timeout_interval *= 2
        else:
            self.timeout_interval = self._computed_timeout()
        # record the time at start (we notice expiery by checking against this time)
        self.timer_start = time.time()

    def _stop_timer(self):
        """sets timer to none/stops it"""
        self.timer_start = None

    def _update_rtt(self, sample):
        """estimatedRTT / devRTT update using formula from book and meta parameters
           a helper function called later, does not decide when to update. 
           also does not mess with the timer.
        """
        if self.estimated_rtt is None:   # set to deafult inital. i got the sample/2 thing from the RFC
            self.estimated_rtt = sample
            self.dev_rtt = sample / 2
        else:  # if a measurment has been done
            self.dev_rtt = (1 - BETA) * self.dev_rtt + BETA * \
                abs(sample - self.estimated_rtt)  # variance formula (based on old est value)
            self.estimated_rtt = (1 - ALPHA) * \
                self.estimated_rtt + ALPHA * sample  # estimated rtt formula.

    # ACK logic
    def handle_ack(self, ack):
        """handles an ack when called"""
        self.stats["acks_received"] += 1  # update stat

        if ack > self.base:
            # case where we got a new ack for a previously unacked packet /packets
            newest = ack - 1  # for printing/logging puprouses only
            # if we have a RTT measurment timer running and the measurment is for a packet that is coverd by the ack
            if self.timed_seq is not None and ack > self.timed_seq:
                # calculate the new sampple RTT
                self._update_rtt(time.time() - self.timed_start)
                self.timed_seq = None  # set it to none so the next packet sent gets timed
            # set state of all packets covverd by the ack to acked
            for s in range(self.base, min(ack, self.total)):
                self.state[s] = ACKED
            self.log(f"ACK {ack if ack < self.total else 'END'} received "
                     # print the acked packets
                     f"→ packets {self.base}–{newest} acknowledged", "green")
            self.base = ack   # slide the window
            self.dup_count = 0  # new ack means not duplicate so resest
            # what to do with the timer?
            if self.base >= self.total:    # in this case we are done transmitting
                self._stop_timer()
                self.done = True
            elif self.base < self.next_seq:      # still more packets sent that need to be acked
                self._start_timer()              # resest timer to new oldset packet
            else:  # not done the entire file, but nothing flying
                self._stop_timer()
            self.show_window()  # print whats going on

        elif ack == self.base:
            # duplicate ack recived, reciver hasent recived the base packet yet
            self.stats["duplicate_acks"] += 1  # update stat
            self.dup_count += 1  # update the number of consequitive duplicates
            self.log(f"DUP ACK {ack} (#{self.dup_count})",
                     "yellow")  # print the new duplicate
            # fast retransmit case and still packets to send
            if self.dup_count == DUP_ACK_THRESHOLD and self.base < self.total:
                self.stats["fast_retransmits"] += 1  # update stat
                self.log(f"3 DUP ACKS → RETRANSMIT {self._seq_label(self.base)}",
                         "magenta")  # print fast retransmit
                # transmit the missing packet
                self._transmit(self.base, retransmission=True)
                self.show_window()  # print whats going on
        # if ack is smaller then base then it is ignored

    def _check_for_ack(self):
        """recvfrom is set to wait at most 2ms to get the ack. it returns otherwise
           so that the loop can retry. it handles one ack at a time, if multiple acks come it 
           handles them individualy, but its fast so thats fine.
           """
        try:
            # recvfrom is set to delay for at most 2ms
            data, _ = self.sock.recvfrom(2048)
        except (socket.timeout, ConnectionResetError):
            return  # no ACK arrived in 2 ms
        # returns so that it dosent get frozen and contiuos
        if len(data) < HEADER_SIZE:
            # if a packet is smaller then the header, it cant be a valid packet.
            return
        ptype, seq, _length = struct.unpack(
            HEADER_FMT, data[:HEADER_SIZE])  # get header data
        if ptype == TYPE_ACK:
            # its a ack so send its sequence numebr to handle_ack for it to handle
            self.handle_ack(seq)

    # main loop
    def run(self):
        """Send the whole list of packets reliably using previously defined functions. returns the statistics dict."""
        start = time.time()  # record start time for total transfer time later
        self.sock.settimeout(0.002)         # recvfrom waits at most 2 ms

        # loop till end packet is recived and done is set
        while not self.done:
            # fill window with new packets
            sent_new = False  # stores whether or not somthing new has been sent and printing is needed
            # while the next packet to be sent is smaller then base + N (window end) and there are packets left to send
            while self.next_seq < self.base + self.N and self.next_seq < self.total:
                self._transmit(self.next_seq)  # send the next packet
                if self.timer_start is None:     # run retransmission timer if not running yet
                    self._start_timer()
                self.next_seq += 1  # move onto the next segment
                sent_new = True  # a new packet has been sent
            if sent_new:
                self.show_window()  # print out if a new packet has been sent

            # checks for a ack after sending.
            # if no ack is recivied and there is nothing to send, the while loop just loops over the following
            # part until it recives one or times out
            self._check_for_ack()
            if self.done:                   # end segment was  acked so we done
                break

            # check  timer of oldest unacknowledged packet
            if (self.timer_start is not None and  # if a timer is going and timer is greater then timeout interval
                    time.time() - self.timer_start >= self.timeout_interval):
                self.stats["timeouts"] += 1  # add event to stat
                # timer is implictly allways of the base segment so we get its label
                label = self._seq_label(self.base)
                # print out
                self.log(f"TIMEOUT {label} → RETRANSMIT {label}", "red")
                # retransmit smallest not acked segment
                self._transmit(self.base, retransmission=True)
                # reset timer by timeout case (double)
                self._start_timer(after_timeout=True)
                self.show_window()  # print out what happend
        # were out of the while loop so its done
        self.stats["transfer_time"] = time.time() - start  # calc transfet time
         # include in stats for printing
        self.stats["estimated_rtt"] = self.estimated_rtt
        self.stats["dev_rtt"] = self.dev_rtt
        return self.stats  # return stats

    def print_summary(self):
        """sender half of the final summary"""
        s = self.stats
        line = self._c("bold", "=" * 52)  # makes a line \__'-'__/
        print(line)
        print(self._c("bold", "  SENDER SUMMARY (Member 2 — window & retransmission)"))
        print(line)
        print(f"  Packets in file (incl. END) : {self.total}")
        print(f"  New packets sent            : {s['new_packets']}")
        print(f"  Total transmissions         : {s['transmissions']}")
        print(f"  Retransmissions             : {s['retransmissions']}")
        print(f"     ├ by timeout             : {s['timeouts']}")
        print(f"     └ by fast retransmit     : {s['fast_retransmits']}")
        print(f"  ACKs received               : {s['acks_received']}")
        print(f"     └ of which duplicates    : {s['duplicate_acks']}")
        print(f"  Transfer time               : {s['transfer_time']:.3f} s")
        if self.estimated_rtt is not None:
            print(f"  Final EstimatedRTT / DevRTT : {self.estimated_rtt*1000:.2f} ms / "
                  f"{self.dev_rtt*1000:.2f} ms")
        print(line)
    # pretty printing for a good grade :)
