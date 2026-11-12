# EECE 350 Reliable File Transfer over UDP

A Python 3 project that transfers a file over UDP while handling simulated packet loss and reordering. The receiver reconstructs the file and checks its SHA-256 hash. Only Python standard libraries are used.

## Current status

The packet builder, unreliable channel, sender window, and receiver are uploaded. **The runnable sender startup script (`sender.py`) still needs to be added and connected to the existing modules.** Running `sender_window.py` alone does not start a transfer.

The instructions below describe the uploaded code. Full two-terminal transfer instructions will be added when the sender startup script is available.

## Team responsibilities and files

All current Python modules are in the repository root. Keep them together so their imports work.

| Member | Responsibility | Current files |
| --- | --- | --- |
| Member 1 - Taline Bteddini | File splitting, packet creation, original SHA-256 hash, unreliable channel, and display helpers | `packet.py`, `channel.py`, `display.py` |
| Member 2 - Kassem Haidar | Sliding window, ACK processing, timers, retransmission, fast retransmit, and sender statistics | `sender_window.py` |
| Member 3 - Joe Abou Khalil | Receiver, cumulative ACKs, buffering, duplicate handling, file reconstruction, END handling, and SHA-256 verification | `receiver.py` |

Members 1 and 2 need to connect their components in the sender startup script.

## Shared packet format

The uploaded modules use Python `struct` format `!BIH`. The header is 7 bytes. `!` means network byte order (big-endian).

| Field | Format | Size | Meaning |
| --- | --- | --- | --- |
| Packet type | `B` | 1 byte | DATA = 0, ACK = 1, END = 2 |
| Sequence or ACK number | `I` | 4 bytes | Unsigned packet sequence number or next expected sequence |
| Payload length | `H` | 2 bytes | Unsigned number of payload bytes; excludes the header |

The payload follows the header. All members must keep this format consistent when making changes.

- DATA sequence numbers start at `0` and increase by one per packet, not per byte.
- The default DATA chunk size is 1,024 bytes. The last chunk may be smaller.
- ACK `n` means all packet sequences below `n` have been accepted in order, and `n` is the next expected sequence. ACK packets have no payload and a payload length of `0`.
- If there are `K` DATA packets, their sequences are `0` through `K - 1`, and END uses sequence `K`. Here, `K` is the DATA packet count, not the window size.
- END carries the original file hash as **32 raw SHA-256 bytes**, not the 64-character hexadecimal text.
- Accepting END `K` produces ACK `K + 1`. An empty file has no DATA packets, so its END sequence is `0` and its final ACK is `1`.

### Receiver and final ACK behavior

The receiver writes packets in order. It buffers future packets and repeats the current ACK while an earlier packet is missing. It discards duplicates without writing the same data twice. When a gap is filled, it processes consecutive buffered packets and sends the new cumulative ACK. END is accepted only when its sequence is expected.

The sender includes END in the normal sequence and retransmission process. After accepting END, the receiver closes the output file, calculates its SHA-256 hash, and prints `MATCH` or `MISMATCH`. The final ACK confirms acceptance through END; it does not communicate the hash comparison result to the sender.

The receiver then stays open and resends the final ACK for valid duplicate END packets from the same sender and with the completed END sequence. **Wait for the sender to report completion before pressing Ctrl+C in the receiver terminal.** There is no automatic two-second exit or limit of five duplicate END packets in the current completion loop. Restart the receiver for each new transfer.

## Start the receiver

Install Python 3. No third-party Python packages are required. Clone the repository once, then enter its folder:

```powershell
git clone https://github.com/Joe-Abou-Khalil/EECE-350-Project.git
cd EECE-350-Project
python receiver.py
```

If you already have a current clone, run `python receiver.py` from that folder. On Windows, `py -3 receiver.py` can be used if the Python launcher is installed.

Current settings are constants near the top of `receiver.py`:

| Setting | Current value |
| --- | --- |
| `RECEIVER_IP` | `127.0.0.1` |
| `RECEIVER_PORT` | `5005` |
| `OUTPUT_FILE_NAME` | `received_file.bin` |

The receiver waits for UDP packets. It writes the output in the current working directory and replaces an existing file with the same output name when started.

`127.0.0.1` is for testing both programs on the same computer. For two computers, bind the receiver to its LAN address or `0.0.0.0`, and configure the sender destination with the receiver computer's actual LAN address and port `5005`. The receiver sends ACKs back to the source IP address and port of the received packet.

## Sender integration still required

Members 1 and 2 should add a startup script that:

1. Reads the input file path, receiver address, window size, loss probability, and reorder probability.
2. Calls `packet.build_packets()` to obtain the DATA/END packets and file information.
3. Creates one UDP socket for sending packets and receiving ACKs.
4. Creates `UnreliableChannel` with that socket and the receiver destination.
5. Creates `SenderWindow` with the packets, the same socket, and `channel.send` as its sending function. Both first transmissions and retransmissions must pass through the channel.
6. Calls `display.reset_clock()` and `display.print_settings()`, then starts `SenderWindow.run()`.
7. Handles any remaining held channel packet with `channel.flush()` at completion, prints `SenderWindow.print_summary()` and the values returned by `channel.summary()`, and closes the socket.

The channel probabilities are between `0.0` and `1.0`. Its defaults are zero loss and zero reordering. Choose and document a positive window size in the startup script; there is currently no sender command-line interface.

Add the exact sender command here after the script is uploaded and tested.

## Integration testing checklist

Run these checks after connecting the sender. This is a checklist, not a claim that every scenario has passed on the current repository version.

- [ ] Normal transfer with loss and reordering disabled; compare the original and reconstructed bytes and confirm `MATCH`.
- [ ] Binary file whose size is not a multiple of the chunk size.
- [ ] Empty file.
- [ ] Missing packets followed by retransmission.
- [ ] Out-of-order packets, including END arriving before missing DATA.
- [ ] Duplicate packets, confirming that output bytes are not repeated.
- [ ] Cumulative ACKs: when the next expected sequence is `1`, receiving sequence `2` keeps ACK `1`; receiving `1` then allows the buffered `2` to be processed and produces ACK `3`.
- [ ] Lost final ACK: END is retransmitted and the receiver repeats the final ACK.
- [ ] Intentionally incorrect hash in a correctly formed END packet, producing `MISMATCH`.
- [ ] Settings, channel events, window events, and final statistics are readable.

A temporary Member 3 `test_sender.py` was developed for independent receiver testing, but it is **not currently uploaded to this repository**. If added later, first check that it uses the current packet format and END behavior. It must remain a test tool and must not replace Member 1's sender or Member 2's reliability component.

## Collaboration workflow

Before starting new work from a clean checkout, update `main` and create a branch. For example:

```powershell
git switch main
git pull --ff-only origin main
git switch -c member1-sender
```

Use a separate branch such as `member2-reliability` or `member3-receiver` for the other components. Keep the shared modules in the repository root. Stage only the files belonging to your change, commit them, push your branch, and open a pull request for group review.

Coordinate changes to packet types, header format, ACK meaning, END format, and addresses before merging. Do not commit generated output files or `__pycache__`.

## Contributions and AI assistance

The bulk of the project code must be student-developed, as required by the assignment. Each member must understand, test, and be able to explain their own work in the oral examination.

- The initial Member 3 teaching scaffold, comments, and independent tests were developed with OpenAI Codex.
- Member 1's files contain function-level contribution notes identifying student-written work, work based on Claude references, and AI-generated or AI-assisted sections. Preserve these notes accurately.
- Member 2's file identifies Kassem Haidar as its author. Each member is responsible for documenting any AI or external-code assistance they actually used.
- This README revision was prepared with OpenAI Codex assistance based on the uploaded source files.

Keep contribution and assistance disclosures accurate as the code changes. The group must review this documentation and record its actual integration test results before submission.
