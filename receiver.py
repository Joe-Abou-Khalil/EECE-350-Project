"""Member 3 UDP receiver for the EECE 350 reliable file transfer project.

Member 3: Joe Abou Khalil.
AI assistance: Teaching scaffold developed with OpenAI Codex and reviewed,
tested, and modified by the student.

This program receives packets, validates headers, sends cumulative ACKs,
buffers out-of-order packets, reconstructs the file, and verifies SHA-256.
The protocol constants are provisional until approved by all group members.
"""

# Calculate the SHA-256 hash of the reconstructed file
import hashlib

# Create and control the UDP network socket
import socket

# Convert packet header values between numbers and bytes
import struct

# Measure the short waiting period after the END packet
import time


# Use this computer as the receiver during local testing
RECEIVER_IP = "127.0.0.1"

# Listen for UDP packets on this port
RECEIVER_PORT = 5005

# Allow recvfrom() to read a complete UDP datagram
MAX_DATAGRAM_SIZE = 65535

# Save the received file using this name
OUTPUT_FILE_NAME = "received_file.bin"

# A raw SHA-256 hash always contains 32 bytes
SHA256_DIGEST_SIZE = 32

# Keep listening briefly in case the final ACK is lost
COMPLETION_WAIT_SECONDS = 2

# Provisional protocol values. The group must approve these before integration.
# Use network byte order with a type, sequence number, and payload length
HEADER_FORMAT = "!BIH"

# Calculate how many bytes the header uses
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Give each kind of packet a number that can be placed in the header
DATA_PACKET = 0
ACK_PACKET = 1
END_PACKET = 2

# Convert packet type numbers into readable names for terminal messages
PACKET_TYPE_NAMES = {DATA_PACKET: "DATA", ACK_PACKET: "ACK", END_PACKET: "END"}


def create_receiver_socket():
    """Create a UDP socket and attach it to the receiver address."""
    # Create an IPv4 UDP socket
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Reserve the receiver's IP address and port for this socket
    receiver_socket.bind((RECEIVER_IP, RECEIVER_PORT))

    # Give the ready socket back to the calling function
    return receiver_socket


def parse_packet(packet_bytes):
    """Read and validate a packet header, then return its fields and payload."""
    # A valid packet must contain the complete header
    if len(packet_bytes) < HEADER_SIZE:
        raise ValueError("packet is smaller than the header")

    # Separate the fixed-size header from the remaining payload bytes
    header_bytes = packet_bytes[:HEADER_SIZE]
    payload = packet_bytes[HEADER_SIZE:]

    # Convert the header bytes into the packet type, sequence, and length
    packet_type, sequence_number, declared_length = struct.unpack(HEADER_FORMAT, header_bytes)

    # Reject values that are not one of the three known packet types
    if packet_type not in PACKET_TYPE_NAMES:
        raise ValueError(f"unknown packet type {packet_type}")

    # Make sure the header length agrees with the bytes that actually arrived
    if declared_length != len(payload):
        raise ValueError(
            f"header says {declared_length} payload bytes, "
            f"but packet contains {len(payload)}"
        )

    # Return the checked values so the receiver can process the packet
    return packet_type, sequence_number, payload


def create_ack_packet(next_expected_sequence):
    """Create an ACK whose number is the next DATA sequence expected."""
    # Pack an ACK header with no payload, so its payload length is zero
    return struct.pack(HEADER_FORMAT, ACK_PACKET, next_expected_sequence, 0)


def send_ack(receiver_socket, sender_address, next_expected_sequence):
    """Send a cumulative ACK back to the address that sent the DATA packet."""
    # Build an ACK containing the next sequence number the receiver needs
    ack_packet = create_ack_packet(next_expected_sequence)

    # Send the ACK back to the sender's IP address and port
    receiver_socket.sendto(ack_packet, sender_address)


def accept_packet_payload(packet_type, payload, output_file):
    """Write DATA payloads and return the hash carried by an END packet."""
    # DATA bytes belong to the reconstructed output file
    if packet_type == DATA_PACKET:
        output_file.write(payload)

        # None means that an END packet has not been processed yet
        return None

    # The only other accepted type is END, whose payload is the original hash
    return payload


def receive_datagrams(receiver_socket, output_file):
    """Receive ordered DATA through END and return completion information."""
    # Start by waiting for packet sequence zero
    expected_sequence = 0

    # Store future packets here until the missing earlier packets arrive
    out_of_order_buffer = {}

    # Show the receiver settings before packet processing begins
    print(f"Receiver listening on {RECEIVER_IP}:{RECEIVER_PORT}")
    print(f"Next expected DATA sequence: {expected_sequence}")
    print("Press Ctrl+C to stop the receiver.\n")

    # Keep receiving packets until a valid END packet is accepted
    while True:
        # Wait for one UDP datagram and remember who sent it
        packet_bytes, sender_address = receiver_socket.recvfrom(MAX_DATAGRAM_SIZE)

        # Try to read and validate the packet header
        try:
            packet_type, sequence_number, payload = parse_packet(packet_bytes)
        except ValueError as error:
            # A bad packet is reported and ignored without stopping the receiver
            print(
                f"DISCARD malformed packet from "
                f"{sender_address[0]}:{sender_address[1]}: {error}\n"
            )
            continue

        # ACK packets belong at the sender, so the receiver does not process them
        if packet_type == ACK_PACKET:
            print("IGNORE unexpected ACK received by the receiver\n")
            continue

        # Get a readable name such as DATA or END for event messages
        packet_name = PACKET_TYPE_NAMES[packet_type]

        # END must contain exactly one raw 32-byte SHA-256 hash
        if packet_type == END_PACKET and len(payload) != SHA256_DIGEST_SIZE:
            # Repeat the current ACK because this invalid END was not accepted
            send_ack(receiver_socket, sender_address, expected_sequence)
            print(
                f"DISCARD END seq={sequence_number}: expected a "
                f"{SHA256_DIGEST_SIZE}-byte SHA-256 hash "
                f"-> ACK {expected_sequence}\n"
            )
            continue

        # A larger sequence number means an earlier packet is still missing
        if sequence_number > expected_sequence:
            # Repeat the missing sequence number as a duplicate ACK
            send_ack(receiver_socket, sender_address, expected_sequence)

            # Do not store a second copy if this future packet is already buffered
            if sequence_number in out_of_order_buffer:
                print(
                    f"RECV {packet_name} seq={sequence_number} duplicate already "
                    f"buffered, "
                    f"discarded -> DUP ACK {expected_sequence}\n"
                )
            else:
                # Save the packet type and payload under its sequence number
                out_of_order_buffer[sequence_number] = (packet_type, payload)
                print(
                    f"RECV {packet_name} seq={sequence_number} out of order, "
                    f"buffered "
                    f"-> DUP ACK {expected_sequence}\n"
                )
            continue

        # A smaller sequence number belongs to a packet already accepted earlier
        if sequence_number < expected_sequence:
            # Discard the duplicate and repeat the current cumulative ACK
            send_ack(receiver_socket, sender_address, expected_sequence)
            print(
                f"RECV {packet_name} seq={sequence_number} duplicate already "
                f"accepted, "
                f"discarded -> ACK {expected_sequence}\n"
            )
            continue

        # This is the exact packet the receiver was waiting for
        # Keep a list of everything accepted during this pass for the event log
        accepted_sequences = [sequence_number]

        # Write DATA or save the hash if this is END
        original_hash = accept_packet_payload(packet_type, payload, output_file)

        # Remember the END sequence only when the accepted packet is END
        end_sequence = sequence_number if packet_type == END_PACKET else None

        # Move to the next sequence number the receiver needs
        expected_sequence += 1

        # Process consecutive buffered packets until a gap or END is reached
        while original_hash is None and expected_sequence in out_of_order_buffer:
            # Remove the next expected packet from the buffer
            buffered_type, buffered_payload = out_of_order_buffer.pop(
                expected_sequence
            )

            # Write buffered DATA or save the hash from buffered END
            original_hash = accept_packet_payload(
                buffered_type, buffered_payload, output_file
            )

            # Record this sequence so the terminal can show what was processed
            accepted_sequences.append(expected_sequence)

            # Save the sequence number if the buffered packet was END
            if buffered_type == END_PACKET:
                end_sequence = expected_sequence

            # Move to the following sequence number
            expected_sequence += 1

        # Push all written bytes from Python's file buffer to the output file
        output_file.flush()

        # Tell the sender the next sequence number still needed
        send_ack(receiver_socket, sender_address, expected_sequence)

        # A non-None hash means END was accepted directly or from the buffer
        if original_hash is not None:
            # Report a simple in-order END when no buffered packet was processed
            if len(accepted_sequences) == 1:
                print(
                    f"RECV END seq={end_sequence} in order "
                    f"-> ACK {expected_sequence}\n"
                )
            else:
                # Report the buffered packets processed after a gap was filled
                print(
                    f"RECV {packet_name} seq={sequence_number} fills gap; "
                    f"processed buffered {accepted_sequences[1:]} including END "
                    f"-> ACK {expected_sequence}\n"
                )

            # Give main() the information needed for hashing and final ACK recovery
            return (
                original_hash,
                end_sequence,
                sender_address,
                expected_sequence,
            )

        # If no buffered packet was processed, report a normal in-order DATA event
        if len(accepted_sequences) == 1:
            print(
                f"RECV DATA seq={sequence_number} in order, "
                f"length={len(payload)} -> ACK {expected_sequence}\n"
            )
        else:
            # Leave out the first packet so this list contains only buffered ones
            drained_sequences = accepted_sequences[1:]

            # Report the cumulative ACK after processing the buffered packets
            print(
                f"RECV DATA seq={sequence_number} fills gap; "
                f"processed buffered {drained_sequences} "
                f"-> ACK {expected_sequence}\n"
            )


def calculate_file_hash(file_name):
    """Calculate and return the raw SHA-256 digest of a file on disk."""
    # Create an empty SHA-256 calculation
    sha256 = hashlib.sha256()

    # Open the completed file as bytes without changing it
    with open(file_name, "rb") as reconstructed_file:
        # Read blocks until the end of the file
        while True:
            # Read at most 4096 bytes during this pass
            file_block = reconstructed_file.read(4096)

            # An empty block means there are no more bytes to read
            if not file_block:
                break

            # Add this block to the running hash calculation
            sha256.update(file_block)

    # Return the final raw 32-byte hash
    return sha256.digest()


def wait_for_duplicate_end(
    receiver_socket,
    sender_address,
    end_sequence,
    final_ack,
):
    """Keep answering duplicate END packets until the user presses Ctrl+C."""

    # Wait for packets without a time limit
    receiver_socket.settimeout(None)
    print("Transfer finished. Listening for duplicate END packets.")
    print("Press Ctrl+C after the sender reports completion.")

    while True:
        # Wait for another packet and find out who sent it
        packet_bytes, packet_sender = receiver_socket.recvfrom(
            MAX_DATAGRAM_SIZE
        )

        # Only answer the sender that completed this transfer
        if packet_sender != sender_address:
            continue

        # Read the header and reject malformed packets
        try:
            packet_type, sequence_number, payload = parse_packet(packet_bytes)
        except ValueError:
            continue

        # Check for END with the completed sequence number and a valid hash size
        if (
            packet_type == END_PACKET
            and sequence_number == end_sequence
            and len(payload) == SHA256_DIGEST_SIZE
        ):
            # Repeat the final ACK because the previous copy may have been lost
            send_ack(receiver_socket, sender_address, final_ack)
            print(
                f"RECV duplicate END seq={end_sequence} "
                f"-> resend ACK {final_ack}"
            )

def main():
    """Start the receiver and close its socket when the program stops."""
    # Create and bind the UDP receiver socket
    receiver_socket = create_receiver_socket()

    try:
        # Open a new binary output file and replace an older file with this name
        with open(OUTPUT_FILE_NAME, "wb") as output_file:
            print(f"Writing accepted DATA to {OUTPUT_FILE_NAME}")

            # Receive through END and save the values needed after the file closes
            original_hash, end_sequence, sender_address, final_ack = (
                receive_datagrams(receiver_socket, output_file)
            )

        # Hash the completed file after the with block has closed it
        reconstructed_hash = calculate_file_hash(OUTPUT_FILE_NAME)

        # Display both hashes in readable hexadecimal form
        print(f"Original SHA-256:      {original_hash.hex()}")
        print(f"Reconstructed SHA-256: {reconstructed_hash.hex()}")

        # Matching hashes mean the reconstructed bytes are correct
        if reconstructed_hash == original_hash:
            print("File integrity: MATCH")
        else:
            print("File integrity: MISMATCH")

        # Stay available briefly in case the sender did not receive the final ACK
        wait_for_duplicate_end(
            receiver_socket,
            sender_address,
            end_sequence,
            final_ack,
        )
    except KeyboardInterrupt:
        # Ctrl+C lets the user stop the receiver without a traceback
        print("\nReceiver stopped by the user.")
    finally:
        # Always release the UDP socket, even after an error or Ctrl+C
        receiver_socket.close()


# Run main() only when this file is started directly
if __name__ == "__main__":
    main()
