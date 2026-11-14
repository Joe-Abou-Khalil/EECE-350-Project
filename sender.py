"""
sender.py — EECE 350 Final Project: Reliable File Transfer over UDP
================================================================================
 Main sender script: connects Member 1s packets and Unreliable Channel with
 Member 2 (Kassem Haidar) sliding window, then prints the settings and the final summary.
================================================================================

Run (start receiver.py first, in another terminal):
    python sender.py <file> [-N 8] [--loss 0.1] [--reorder 0.1]
                            [--host 127.0.0.1] [--port 5005] [--chunk 1024] [--seed S]
"""

import argparse  # pareses comand line arguments
import socket  # used to create a UDP socket
import sys  # to error and exit

# import everything needed from the other files
from packet import build_packets, CHUNK_SIZE   # makes the packets
from channel import UnreliableChannel  # unrelaible chanel to send through
# display stuff (print_final_summary added by Member 1)
from display import print_settings, reset_clock, print_final_summary
from sender_window import SenderWindow           # sender


def parse_args():
    """parse the arguments from the terminal."""
    p = argparse.ArgumentParser(
        description="Reliable file transfer over UDP — sender")
    # where the file is
    p.add_argument("file", help="path of the file to send")
    # window size
    p.add_argument("-N", "--window", type=int, default=8,
                   help="window size N: max packets in flight without an ACK (default 8)")
    # loss prob
    p.add_argument("--loss", type=float, default=0.1,
                   help="probability the simulator drops a packet, 0-1 (default 0.1)")
    # reoder probability
    p.add_argument("--reorder", type=float, default=0.1,
                   help="probability the simulator holds a packet back and sends it "
                        "after the next one, 0-1 (default 0.1)")
    # host ip adress
    p.add_argument("--host", default="127.0.0.1",
                   help="receiver IP address (default 127.0.0.1)")
    # reciver port number
    p.add_argument("--port", type=int, default=5005,
                   help="receiver UDP port, must match receiver.py (default 5005)")
    # packet size
    p.add_argument("--chunk", type=int, default=CHUNK_SIZE,
                   help=f"data bytes per packet (default {CHUNK_SIZE})")
    # random seed, for testing
    p.add_argument("--seed", type=int, default=None,
                   help="random seed for the simulator; same seed = same drops "
                        "and reorders (default: random each run)")
    args = p.parse_args()  # stores terminal arguments
    if args.window < 1:  # restriction on window size
        p.error("window size N must be at least 1")
    return args


def main():
    args = parse_args()  # store terminal arguments in args

    try:
        # runs member 1's build packet function with terminal arguments
        packets, info = build_packets(args.file, args.chunk)
    except FileNotFoundError:
        # give up if the packet file is not found
        sys.exit(f"Error: file not found: {args.file}")
    except ValueError as e:
        # something wrong with the packets in the file, chunk size is invalid.
        sys.exit(f"Error: {e}")

    # create a UDP IPv4 socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # try for keyboard interupt and socket end
    try:
        # try to create unreliable chanel
        try:
            # create unreliable chanel
            channel = UnreliableChannel(sock, (args.host, args.port),
                                        args.loss, args.reorder, seed=args.seed)
        except ValueError as e:
            # loss or reorder outside of range
            sys.exit(f"Error: {e}")

        # call display function print for inital settings
        print_settings(info, args.window, args.loss, args.reorder)

        # instantiate a instance of senderwindow to use.
        window = SenderWindow(packets, sock, channel.send, args.window)
        reset_clock()          # set time to 0 in display functions
        # call for sender window to actually send everything, and saves the stats from the run
        stats = window.run()
        channel.flush()  # sends any remaning packets remaining (since it ended, they are unneeded)

        # final summary (display.py, Member 1)
        print_final_summary(stats, channel.summary())

    except KeyboardInterrupt:
        # keyboard interputok
        print("\nSender stopped by the user.")
    finally:
        # close socket regardless of any errors or exceptions
        sock.close()


if __name__ == "__main__":
    main()
