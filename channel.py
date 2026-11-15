# channel.py  —  Unreliable Channel (Simulator)
# Author: Taline Bteddini  (Member 1)
#
# CONTRIBUTIONS IN THIS FILE
#   Written by Member 1: loss decision, reorder (hold/release), normal send
#                        path, _transmit, summary, flush
#   Written by Member 1 from an AI-generated reference (Claude, Anthropic):
#                        input validation
#   AI-generated (Claude, Anthropic), reviewed by Member 1: thread lock
# Not part of the protocol: stands in for a real network. Member 2 calls channel.send(pkt) instead of sock.sendto().
import random
import threading
from packet import END, parse_packet
from display import log_event

def _label(ptype, seq):
    return f"END({seq})" if ptype == END else str(seq)


class UnreliableChannel:
    def __init__(self, sock, dest, loss=0.0, reorder=0.0, seed=None, log=None):
        #Member 1 (from AI-generated reference)
        for name, p in (("loss", loss), ("reorder", reorder)):
            if not 0.0 <= p <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")

        #Member 1 
        self.sock = sock
        self.dest = dest
        self.loss = loss
        self.reorder = reorder
        self.rng = random.Random(seed)   # own generator -> same seed, same run
        self.log = log or (lambda kind, text: log_event("CHANNEL", kind, text))
        self.stats = {"handed": 0, "sent": 0, "dropped": 0, "reordered": 0}
        self.held = None                 # the one packet being held back, or None
        self.held_label = None           # its label, for the log

        #AI-generated (Claude)
        # Member 2 may call send() from more than one thread (main loop + timer)
        self.lock = threading.Lock()

    def send(self, packet):
        ptype, seq, _ = parse_packet(packet)
        label = _label(ptype, seq)

        with self.lock:
            self.stats["handed"] += 1

            # Member 1: loss (checked first)
            if self.rng.random() < self.loss:
                self.stats["dropped"] += 1
                self.log("DROP", f"DROPPED {label} (simulated)")
                return

            #Member 1: reorder
            if self.held is not None:
                self._transmit(packet)
                self._transmit(self.held)
                self.stats["reordered"] += 1
                self.log("REORDER", f"REORDERED {self.held_label} after {label}")
                self.held = None
                self.held_label = None
                return

            
            #Member 1
            if self.rng.random() < self.reorder:
                self.held = packet
                self.held_label = label
                self.log("HOLD", f"HOLDING {label} (will send after next packet)")
                return
            self._transmit(packet)

    def flush(self):
       with self.lock:
            if self.held is None:
                return
            self._transmit(self.held)
            self.log("FLUSH", f"RELEASED {self.held_label} (flush)")
            self.held = None
            self.held_label = None
    #Member 1
    def summary(self):
        with self.lock:
            return dict(self.stats)

    #Member 1
    def _transmit(self, packet):
        self.sock.sendto(packet, self.dest)
        self.stats["sent"] += 1
