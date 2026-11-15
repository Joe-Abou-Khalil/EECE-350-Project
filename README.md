# EECE 350 - Reliable File Transfer over UDP

This is our Computer Networks final project. We use Python 3 to send a file over UDP, simulate packet loss and reordering, and recover missing packets. The receiver puts the file back together and checks its SHA-256 hash. Everything uses Python standard libraries.

## Our parts

- Taline Bteddini (Member 1): packet creation, file splitting, channel simulator and display helpers. Files: `packet.py`, `channel.py`, `display.py`.
- Kassem Haidar (Member 2): sliding window, timers, ACK handling and retransmissions. File: `sender_window.py`.
- Joe Abou Khalil (Member 3): receiver, buffering, cumulative ACKs, file reconstruction and hash checking. File: `receiver.py`.

`sender.py` connects the sender components. Keep all the Python files in the same folder.

## Before running

As of November 15, the sender and final summary are uploaded, but there is an extra `§` at the start of line 1 in `sender_window.py`. It needs to be removed before the sender can run. The commands below are for after that fix.

Pull request #3 contains receiver display changes and is still separate from `main`.

## How to run it

Download or clone the repository and open two terminals in its folder. Start the receiver first:

```powershell
python -X utf8 receiver.py
```

In the second terminal, run the sender. This example sends the README itself so no extra test file is needed:

```powershell
python -X utf8 sender.py README.md -N 8 --loss 0 --reorder 0
```

Replace `README.md` with the path of the file you want to send. Put the path in quotes if it contains spaces.

To try loss and reordering:

```powershell
python -X utf8 sender.py README.md -N 8 --loss 0.2 --reorder 0.5 --seed 7
```

The receiver saves the file as `received_file.bin` and prints `MATCH` or `MISMATCH`. It stays open to answer duplicate END packets in case the last ACK was lost. Wait for the sender to finish, then press Ctrl+C in the receiver terminal. Restart the receiver before each new transfer. Starting it again replaces the previous output file.

On PowerShell, you can also compare the hashes yourself:

```powershell
Get-FileHash README.md -Algorithm SHA256
Get-FileHash received_file.bin -Algorithm SHA256
```

## Settings

| Sender option | Default | Meaning |
| --- | --- | --- |
| `-N` or `--window` | 8 | Maximum number of packets waiting for ACKs |
| `--loss` | 0.1 | Packet-drop probability |
| `--reorder` | 0.1 | Probability of holding a packet to send it later |
| `--chunk` | 1024 | Data bytes per packet |
| `--host` | 127.0.0.1 | Receiver IP address |
| `--port` | 5005 | Receiver UDP port |
| `--seed` | None | Optional seed for the channel random generator |

Use `--loss 0 --reorder 0` for a normal transfer. The receiver address, port and output filename are constants near the top of `receiver.py`. The default address is for testing on one computer. For two computers, bind the receiver to its LAN address or `0.0.0.0`, then give the sender the receiver computer's actual LAN address. ACKs go back to the sender's source port.

## Packet format and ACKs

The header uses `struct` format `!BIH`, which is 7 bytes in network byte order:

| Field | Size | Value |
| --- | --- | --- |
| Type | 1 byte | DATA = 0, ACK = 1, END = 2 |
| Sequence / ACK number | 4 bytes | Unsigned number |
| Payload length | 2 bytes | Number of bytes after the header |

DATA packets start at sequence 0. ACK 3 means packets 0, 1 and 2 were accepted in order, and packet 3 is needed next. ACKs have no payload.

If packet 2 arrives while the receiver is waiting for 1, it buffers 2 and repeats ACK 1. When 1 arrives, it writes both packets and sends ACK 3. Duplicates are discarded so the same bytes are not written twice.

END uses the sequence after the last DATA packet and carries the original file's raw 32-byte SHA-256 hash. The receiver accepts END in order and ACKs the next sequence. For an empty file, END is 0 and its ACK is 1. The final ACK confirms receipt; the hash result is shown in the receiver terminal.

## Testing and remaining work

An isolated copy of commit `97a6744` passed normal transfer, loss, reordering, combined loss/reordering and empty-file checks on November 14. The reconstructed bytes and hashes matched. Those results belong to that version, not the newer code.

Before submission, fix the startup character and repeat those tests on the final version. Also test duplicate packets, a lost final ACK and an intentionally wrong END hash. Review the pending receiver display changes before merging them.

The sender now prints transfer statistics, including drops, reordering, retransmissions, timeouts and elapsed time. Check the receiver terminal for the file integrity result.

## AI assistance

Member 1's files identify the sections written with Claude assistance. The initial Member 3 scaffold, comments and independent tests were developed with OpenAI Codex. This README was also revised with Codex assistance. Each member should keep their contribution notes accurate, document any other assistance used, and be able to explain their code.
