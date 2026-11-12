# =============================================================================
# packet.py  —  Packet format, file splitting, END packet
# Author: Taline Bteddini  (Member 1)
#
# CONTRIBUTIONS IN THIS FILE
#   Written by Member 1: header format, make_ack
#   Written by Member 1 from an AI-generated reference (Claude, Anthropic):
#                        make_packet, parse_packet, build_packets
#   AI-assisted (Claude, Anthropic): module layout and constants;
#                        reviewed by Member 1.
# =============================================================================
import hashlib
import os
import struct

DATA = 0
ACK = 1
END = 2
TYPE_NAMES = {DATA: "DATA", ACK: "ACK", END: "END"}

# ---- Header format — Member 1 ----
HEADER_FMT = "!BIH"
HEADER_SIZE = struct.calcsize(HEADER_FMT)

CHUNK_SIZE = 1024
MAX_UDP_PAYLOAD = 65507
MAX_CHUNK_SIZE = MAX_UDP_PAYLOAD - HEADER_SIZE
RECV_BUFFER = 65535


# ---- Member 1 (from AI-generated reference) ----
def make_packet(ptype, seq, data=b""):
    if ptype not in TYPE_NAMES:
        raise ValueError(f"unknown packet type {ptype}")
    if len(data) > 0xFFFF:
        raise ValueError("payload too large for the 2-byte length field")
    header = struct.pack(HEADER_FMT, ptype, seq, len(data))
    return header + data


# ---- Member 1 (from AI-generated reference) ----
def parse_packet(raw):
    if len(raw) < HEADER_SIZE:
        raise ValueError("packet shorter than header")
    ptype, seq, length = struct.unpack(HEADER_FMT, raw[:HEADER_SIZE])
    if ptype not in TYPE_NAMES:
        raise ValueError(f"unknown packet type {ptype}")
    data = raw[HEADER_SIZE:HEADER_SIZE + length]
    if len(data) != length:
        raise ValueError("payload shorter than the length field says")
    return ptype, seq, data


# ---- Member 1 ----
def make_ack(next_expected):
    return make_packet(ACK, next_expected)


# ---- Member 1 (from AI-generated reference) ----
def build_packets(path, chunk_size=CHUNK_SIZE):
    if not 1 <= chunk_size <= MAX_CHUNK_SIZE:
        raise ValueError(f"chunk size must be between 1 and {MAX_CHUNK_SIZE}")
    with open(path, "rb") as f:
        content = f.read()
    packets = []
    for seq, offset in enumerate(range(0, len(content), chunk_size)):
        chunk = content[offset:offset + chunk_size]
        packets.append(make_packet(DATA, seq, chunk))
    digest = hashlib.sha256(content).digest()
    end_seq = len(packets)
    packets.append(make_packet(END, end_seq, digest))
    info = {
        "file_name": os.path.basename(path),
        "file_size": len(content),
        "chunk_size": chunk_size,
        "data_packets": end_seq,
        "total_packets": end_seq + 1,
        "end_seq": end_seq,
        "sha256": digest.hex(),
    }
    return packets, info