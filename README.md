# DuelMesh

DuelMesh is a two-player terminal duel game for Meshtastic LoRa meshes. It works peer-to-peer: no server, no internet, no cloud service, and no third referee node.

Two players clone the repo, connect one Meshtastic node each, join the same mesh/channel, and play from the terminal.

## What You Need

- Python 3.10+
- Two Meshtastic-compatible LoRa devices, for example two Heltec V3 boards
- Both devices flashed with Meshtastic firmware
- Both devices configured for the same LoRa region and same primary channel
- A USB cable for each device if both players are testing from laptops

## Install

Clone the repo:

```bash
git clone https://github.com/YOUR_USER/DuelMesh.git
cd DuelMesh
```

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install DuelMesh for Meshtastic hardware:

```bash
pip install -e ".[lora]"
```

For development and tests:

```bash
pip install -e ".[test,lora]"
pytest
```

## Verify The Meshtastic Devices

Find the serial ports.

macOS:

```bash
ls /dev/cu.*
```

Linux:

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Windows uses ports such as `COM4`.

Check each device:

```bash
meshtastic --port /dev/cu.YOUR_DEVICE --info
```

Send a plain Meshtastic test message before testing DuelMesh:

Terminal A:

```bash
meshtastic --port /dev/cu.HELTEC_A --sendtext "hello from A"
```

Terminal B:

```bash
meshtastic --port /dev/cu.HELTEC_B --listen
```

If this does not work, fix Meshtastic first: region, channel, firmware, antenna, distance, or serial port.

## Start A Real LoRa Duel

Player A:

```bash
duelmesh --transport lora --port /dev/cu.HELTEC_A --nick Alice --data-dir .duelmesh/alice-lora
```

Player B:

```bash
duelmesh --transport lora --port /dev/cu.HELTEC_B --nick Bob --data-dir .duelmesh/bob-lora
```

Bluetooth LE is also supported if your Meshtastic Python install and OS BLE stack can connect to the device:

```bash
duelmesh --transport lora --ble "DEVICE_NAME_OR_ADDRESS" --nick Alice --data-dir .duelmesh/alice-ble
```

Use either `--port` or `--ble`, not both. USB serial is recommended for first tests because it is easier to debug.

Player A opens a game:

```text
/open
```

Player B lists games and joins:

```text
/games
/join GAME_ID
```

Both players roll:

```text
/roll
```

If the dice draw, both players use `/roll` again. When there is a winner, DuelMesh automatically opens the ATK/DEF selector for the player with initiative.

## Local Test Without LoRa

You can test two players on one machine with the mock mesh.

Terminal A:

```bash
duelmesh --transport mock --nick Alice
```

Terminal B:

```bash
duelmesh --transport mock --nick Bob
```

Then use the same flow:

```text
/open
/games
/join GAME_ID
/roll
```

In mock mode, different `--nick` values automatically create separate local profiles. Both clients share `.duelmesh/mockmesh` as the simulated radio bus.

## Commands

```text
/open              Create public duel offer
/games             List open games heard on the mesh
/join GAME_ID      Join an open game
/status            Show profile, HP, round, and connection
/roll              Roll a d6 for first initiative
/reveal            Send current reveal again if needed
/cancel            Cancel open or active duel
/nick NEWNAME      Change nickname
/profile           Show local profile and record
/help              Show commands
/quit              Save and exit
```

If you have an open game and run `/join GAME_ID`, DuelMesh warns that your open game will be removed from the mesh lobby. Confirming with `y` closes your offer first, then sends the join request.

## Duel Rules

Each player has 10 HP and three target zones:

```text
1 Head  = 2 damage
2 Body  = 1 damage
3 Legs  = 0.5 damage
```

Each round both players choose:

```text
ATK: target to attack
DEF: target to defend
```

If your DEF matches the opponent's ATK, you block that attack. Otherwise you take the target damage.

Example:

```text
Alice: ATK Head, DEF Head
Bob:   ATK Body, DEF Body
```

Result:

```text
Alice hits Bob's Head: Bob takes 2
Bob hits Alice's Body: Alice takes 1
```

Both players can take damage in the same round.

## Anti-Cheat Model

DuelMesh has no third server node. Both clients calculate the same deterministic result.

Before dueling, clients compare:

```text
ruleset
rules_hash
```

Each turn uses commit-reveal:

```text
commit = SHA256(round + atk + def + salt)
```

Flow:

```text
1. Player with initiative commits ATK/DEF.
2. Other player commits ATK/DEF.
3. Both clients reveal ATK/DEF/salt.
4. Both clients verify commits.
5. Both clients calculate damage locally.
```

At the end, the duel history can be replayed. If the replay does not match, DuelMesh prints:

```text
CHEATING OR CLIENT MISMATCH DETECTED
```

Without a server, a malicious modified client cannot be prevented absolutely, but mismatches are detectable with rules hashes, commit-reveal, and replay verification.

## Packet Types

DuelMesh sends compact JSON text packets over Meshtastic:

```text
offer       advertise open game
close       remove an open lobby offer
join        request to join
accept      accept join
roll        d6 initiative roll
commit      committed ATK/DEF hash
reveal      revealed ATK/DEF/salt
cancel      cancel game
forfeit     surrender when closing active CLI
```

Lobby packets use the primary Meshtastic channel. Duel packets are sent directly to the opponent node ID after pairing.

## Troubleshooting

No games appear in `/games`:

- Confirm both devices are on the same Meshtastic primary channel.
- Confirm both devices use the same LoRa region.
- Test with `meshtastic --sendtext` and `meshtastic --listen`.
- Keep both antennas connected before powering the radios.
- Use `/open` again; lobby offers expire if not reannounced.

Only my own game appears in mock mode:

- Use different nicknames:

```bash
duelmesh --transport mock --nick Alice
duelmesh --transport mock --nick Bob
```

Hardware serial port is wrong:

- Use `meshtastic --port PORT --info` until you find the correct port.
- On macOS, Heltec boards usually appear under `/dev/cu.*`.

Bluetooth does not connect:

- First test with the Meshtastic CLI using `meshtastic --ble "DEVICE_NAME_OR_ADDRESS" --info`.
- Pair/trust the device in your OS Bluetooth settings if your platform requires it.
- Fall back to USB serial for the first DuelMesh test.

The duel gets stuck after a packet loss:

- Use `/status` on both clients.
- Use `/reveal` if both already committed but one reveal was missed.
- Use `/cancel` and start a new duel if one device went offline.

## Notes For Heltec V3

- Flash both boards with current Meshtastic firmware for Heltec V3.
- Configure the correct regional frequency for your country.
- Use the same channel URL or QR configuration on both devices.
- Keep antennas attached.
- For close-range desk testing, do not place both radios directly touching each other; a little separation is healthier for reception.
