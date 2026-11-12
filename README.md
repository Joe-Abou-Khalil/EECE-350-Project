# EECE 350 Reliable File Transfer over UDP

This repository is the shared workspace for the three-member EECE 350 final project.

## Team responsibilities

- **Member 1:** sender, packet creation, file splitting, and unreliable-channel simulator. Add working files under `member1/`.
- **Member 2:** sliding window, timers, retransmission, and fast retransmit. Add working files under `member2/`.
- **Member 3 - Joe Abou Khalil:** receiver, cumulative acknowledgements, buffering, file reconstruction, END handling, and SHA-256 verification. The main file is `receiver.py`.

`test_sender.py` is a temporary scripted tool for testing the receiver independently. It does not replace the real sender or reliability components.

## Provisional shared packet format

The current receiver uses Python `struct` format `!BIH`:

| Field | Size | Meaning |
| --- | ---: | --- |
| Packet type | 1 byte | DATA = 1, ACK = 2, END = 3 |
| Sequence or ACK number | 4 bytes | Unsigned integer |
| Payload length | 2 bytes | Number of payload bytes |

Additional provisional rules:

- DATA sequence numbers start at 0.
- ACK `n` means `n` is the next packet expected.
- If there are `N` DATA packets, END uses sequence number `N`.
- END carries the raw 32-byte SHA-256 digest.
- Accepting END `N` produces ACK `N + 1`.
- Local receiver address: `127.0.0.1:5005`.

All members must approve these rules before integration.

## Testing Member 3's receiver

Open two terminals in the repository folder.

Terminal 1:

```powershell
python receiver.py
```

Terminal 2 - matching hash:

```powershell
python test_sender.py
```

Terminal 2 - intentional hash mismatch:

```powershell
python test_sender.py --mismatch
```

## Collaboration workflow

Each member should clone the repository, place work in the assigned folder, and use a separate branch:

```powershell
git clone https://github.com/Joe-Abou-Khalil/EECE-350-Project.git
cd EECE-350-Project
git switch -c member1-sender
```

Member 2 should use a branch such as `member2-reliability`. After editing:

```powershell
git add .
git commit -m "Add sender component"
git push -u origin member1-sender
```

Then open a pull request on GitHub so the group can review the changes before merging them into `main`.

## AI assistance disclosure

The initial Member 3 teaching scaffold, comments, and independent tests were developed with OpenAI Codex. The student must review, understand, test, and document any AI-assisted code in accordance with the project instructions.
