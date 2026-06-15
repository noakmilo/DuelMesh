# DuelMesh — Codex Build Prompt

Create a complete Python CLI game called **DuelMesh** that runs over **Meshtastic LoRa**.

DuelMesh is a two-player off-grid ASCII duel game inspired by simple Telegram-style duel mechanics, adapted specifically for low-bandwidth Meshtastic mesh networks.

The final result must be a real runnable project, not pseudocode.

---

## 1. Core Concept

Build a two-player off-grid duel game over Meshtastic.

Each player has:

- HP: 10
- Three target zones:
  - Head
  - Body
  - Legs

Damage values:

- Head = 2 HP damage
- Body = 1 HP damage
- Legs = 0.5 HP damage

Each round, both players secretly choose:

- ATK: where they attack
- DEF: what they defend

Example:

Player 1:
- ATK = Head
- DEF = Body

Player 2:
- ATK = Body
- DEF = Legs

Resolution:

- Player 1 attacks Head.
- Player 2 defended Legs.
- Player 1 hits Head.
- Player 2 loses 2 HP.

- Player 2 attacks Body.
- Player 1 defended Body.
- Player 2 is blocked.
- Player 1 loses 0 HP.

The duel continues until one player reaches 0 HP.

If both players reach 0 HP in the same round, result is a draw.

---

## 2. Important Design Goal

This game must be designed specifically for Meshtastic.

That means:

- Very small packets
- No server
- No internet
- No cloud
- No central authority
- No always-online dependency
- Works over unreliable LoRa links
- Handles delayed, duplicated, and lost packets
- Supports direct messages after pairing
- Uses a public discovery channel only for lobby traffic

---

## 3. Technology Requirements

Use:

- Python 3.10+
- meshtastic Python library
- pubsub
- argparse
- dataclasses where useful
- type hints
- JSON for protocol and save files
- pytest for tests

Do not use:

- Internet networking
- External servers
- Cloud APIs
- WebSockets
- Databases
- GUI frameworks

The game must run in a terminal.

---

## 4. Project Structure

Generate the complete codebase:

```text
duelmesh/
    __init__.py
    cli.py
    game.py
    protocol.py
    transport.py
    storage.py
    lobby.py
    ascii_ui.py
    config.py
    node_setup.py

tests/
    test_game.py
    test_protocol.py
    test_lobby.py
    test_commit_reveal.py
    test_transport_mock.py
    test_ascii_ui.py

README.md
requirements.txt
pyproject.toml
```

Return every file with complete implementation.

---

## 5. CLI Commands

The application must support these commands:

```text
/open
/games
/join GAME_ID
/status
/duel
/reveal
/cancel
/help
/quit
```

### /open

Creates a public duel offer on the MeshGames channel.

### /games

Lists open games heard on the mesh.

### /join GAME_ID

Attempts to join an open game.

### /status

Shows current game state, HP, round, opponent, and connection status.

### /duel

Starts the turn selection UI.

The CLI must ask the player step by step.

Do not require users to type words like "head" or "body".

Use numeric menu selection to avoid typos.

Example:

```text
Choose ATK:

1) Head  -2 HP
2) Body  -1 HP
3) Legs  -0.5 HP

ATK? 1
```

Then:

```text
Choose DEF:

1) Head
2) Body
3) Legs

DEF? 2
```

Then show confirmation:

```text
You selected:

ATK: Head
DEF: Body

Lock turn? y/n
```

Only after confirmation should the turn be committed and sent.

### /reveal

Reveals turn salt/history if commit-reveal is enabled, or final duel proof if needed.

### /cancel

Cancels an open or active duel.

### /help

Shows all commands.

### /quit

Exits safely and saves current state.

---

## 6. ASCII Gaming UI

The CLI should feel like a game, not a raw script.

Implement a dedicated `ascii_ui.py` module.

The UI must include:

- Title screen
- Lobby screen
- Status screen
- Round selection screen
- ASCII body target
- HP bars
- Round result screen
- Victory/defeat/draw screen
- Waiting screen

Use only plain terminal ASCII/Unicode characters.

No curses dependency required.

Keep it simple and portable.

Example title/status style:

```text
╔══════════════════════════════════════╗
║              DUELMESH                ║
║          OFF-GRID MESH DUEL          ║
║             GAME: K7Q4               ║
╠══════════════════════════════════════╣
║ YOU        HP: ████████░░  8.0 / 10  ║
║ ENEMY      HP: ██████░░░░  6.0 / 10  ║
╠══════════════════════════════════════╣
║ ROUND 4                              ║
╚══════════════════════════════════════╝
```

ASCII body:

```text
        [1] HEAD
            O

        [2] BODY
           /|\

        [3] LEGS
           / \
```

When selecting attack target, show the chosen zone highlighted with a pointer:

```text
        > [1] HEAD
              O

          [2] BODY
             /|\

          [3] LEGS
             / \
```

For result screens:

```text
╔══════════════════════════════════════╗
║             ROUND RESULT             ║
╠══════════════════════════════════════╣
║ YOU attacked:    HEAD                ║
║ ENEMY defended:  LEGS                ║
║ RESULT: HIT                          ║
║ DAMAGE: -2.0 HP                      ║
║                                      ║
║ ENEMY attacked:  BODY                ║
║ YOU defended:    BODY                ║
║ RESULT: BLOCKED                      ║
║ DAMAGE: 0 HP                         ║
╠══════════════════════════════════════╣
║ YOU HP:    8.0 / 10                  ║
║ ENEMY HP:  4.0 / 10                  ║
╚══════════════════════════════════════╝
```

HP bar function:

- Full HP: `██████████`
- Half HP: `█████░░░░░`
- Critical: `█░░░░░░░░░`

---

## 7. Game Rules

Default HP:

```text
10.0
```

Damage table:

```text
Head = 2.0
Body = 1.0
Legs = 0.5
```

Both players choose one attack and one defense per round.

A hit occurs when:

```text
attacker_attack_zone != defender_defense_zone
```

A block occurs when:

```text
attacker_attack_zone == defender_defense_zone
```

Round resolution is simultaneous.

Both players can damage each other in the same round.

Possible outcomes:

- Player wins
- Player loses
- Draw
- Opponent disconnects or cancels

---

## 8. Two-Player Lock Requirement

A game must support exactly two players:

- Host
- Guest

Game states:

```text
OPEN
LOCKED
IN_PROGRESS
FINISHED
CANCELLED
```

Workflow:

1. Host creates `/open` game.
2. Host broadcasts an offer.
3. First valid `/join GAME_ID` is accepted.
4. Game state becomes LOCKED.
5. Host stores accepted guest node ID.
6. Guest stores host node ID.
7. Host sends `start` directly to accepted guest.
8. Gameplay begins only after both players acknowledge start.

Any later join request must be rejected.

Send a compact full packet:

```json
{"a":"dm","v":1,"t":"full","g":"K7Q4"}
```

Third-party packets must not affect game state.

Ignore gameplay packets unless:

```text
sender == opponent_node_id
```

Tests must prove:

- First join succeeds
- Second join is rejected
- Third-party turn packet is ignored
- Third-party reveal packet is ignored
- Only host and accepted guest can change game state

---

## 9. Lobby / Discovery

Use a dedicated public Meshtastic channel for discovery.

Default channel index:

```text
1
```

Recommended channel name:

```text
MeshGames
```

Public discovery channel should only be used for:

- offer
- join
- full
- cancel

After pairing, use direct messages whenever possible for:

- start
- turn_commit
- turn_reveal
- result
- ack
- reveal_final

Open games should have expiration.

Default expiration:

```text
10 minutes
```

`/games` should show:

```text
╔══════════════════════════════════════╗
║              OPEN GAMES              ║
╠══════════════════════════════════════╣
║ K7Q4  DuelMesh  NODE_A1F3  Waiting   ║
║ M2LP  DuelMesh  NODE_C882  Waiting   ║
╚══════════════════════════════════════╝
```

---

## 10. Meshtastic Node Configuration Requirements

Include a `node_setup.py` helper module and README instructions for configuring a Meshtastic node.

The app should not silently change radio settings unless the user explicitly runs a setup command.

Add optional CLI startup command:

```text
--setup-node
```

When run, it should:

1. Connect to the Meshtastic device.
2. Read basic node info.
3. Display:
   - Node ID
   - Long name
   - Short name
   - Region
   - Modem preset if available
   - Available channels
4. Check whether a secondary channel exists at channel index 1.
5. Recommend creating a MeshGames channel if missing.
6. Offer instructions to configure it manually if automatic configuration is not implemented.

The README must include manual Meshtastic configuration steps:

Recommended node setup:

```text
Primary channel:
- Keep normal local mesh / public channel
- Do not use for game traffic

Secondary channel:
- Name: MeshGames
- Role: public game discovery
- Channel index: 1
- PSK: default public PSK or a shared group PSK
- Uplink/downlink: disabled unless the user intentionally wants MQTT
```

Recommended app settings:

```text
Region: user's legal region
Modem preset: LongFast or local community default
Bluetooth/Serial: enabled depending on device connection
Client connection: USB serial recommended for reliability
```

Important legal note:

```text
Users must configure their Meshtastic device according to their local radio laws and band plan.
Do not hardcode region or transmit settings.
Do not automatically change region.
```

The app should support:

```text
--port /dev/ttyUSB0
--port COM3
--channel-index 1
--mock
--node-name Camilo
--setup-node
```

If no device is found:

Display a friendly message:

```text
No Meshtastic device found.

Try:
- Connect your node by USB
- Check your serial port
- Run with --port /dev/ttyUSB0 or --port COM3
- Use --mock for local testing
```

---

## 11. Compact Protocol

Use compact JSON to save LoRa bandwidth.

Every packet should contain:

```text
a = app identifier
v = protocol version
t = message type
g = game_id
s = sender node id/name
m = message id
ts = timestamp
```

Recommended app identifier:

```text
dm
```

Meaning:

```text
DuelMesh
```

Example offer:

```json
{"a":"dm","v":1,"t":"offer","g":"K7Q4","s":"NODE_A1F3","m":"abc123","ts":1710000000}
```

Example join:

```json
{"a":"dm","v":1,"t":"join","g":"K7Q4","s":"NODE_B92C","m":"def456","ts":1710000010}
```

Example full:

```json
{"a":"dm","v":1,"t":"full","g":"K7Q4","s":"NODE_A1F3","m":"ghi789","ts":1710000020}
```

Turn messages should be compact.

Zone mapping:

```text
1 = Head
2 = Body
3 = Legs
```

Do not send strings like "head" in turn packets.

Use numbers:

```json
{"a":"dm","v":1,"t":"turn_commit","g":"K7Q4","r":4,"c":"hash","s":"NODE_A1F3","m":"x1","ts":1710000030}
```

Then reveal after both commits are received:

```json
{"a":"dm","v":1,"t":"turn_reveal","g":"K7Q4","r":4,"atk":1,"def":2,"salt":"abc","s":"NODE_A1F3","m":"x2","ts":1710000040}
```

---

## 12. Commit-Reveal Per Round

To prevent cheating, do not send raw ATK/DEF immediately.

Use commit-reveal each round:

1. Player selects ATK and DEF locally.
2. Generate random salt.
3. Create commit hash:

```text
SHA256(game_id + round_number + atk + def + salt)
```

4. Send `turn_commit`.
5. Wait for opponent `turn_commit`.
6. After both commits are received, send `turn_reveal`.
7. Verify opponent reveal matches opponent commit.
8. Resolve round.

If reveal does not match commit:

```text
CHEATING DETECTED
```

If opponent never reveals:

```text
Opponent did not reveal. Round unresolved.
```

This prevents a player from waiting to see the opponent's ATK/DEF before choosing.

---

## 13. ACK / Retry

Implement ACK for important packets:

- join
- start
- turn_commit
- turn_reveal
- result
- cancel
- full

Each important outgoing packet should be stored as pending until ACK is received.

Retry:

```text
max retries = 3
```

Retry delay:

```text
5 seconds default
```

The app must ignore duplicate messages using `msg_id`.

ACK packet:

```json
{"a":"dm","v":1,"t":"ack","g":"K7Q4","ack":"msg_id_here","s":"NODE_B92C","m":"ack123","ts":1710000050}
```

---

## 14. Local State / Resume

Save game state locally as JSON.

Default file:

```text
duelmesh_state.json
```

Store:

- Current game ID
- Role
- Opponent node ID
- HP values
- Round number
- Game state
- Pending messages
- Processed message IDs
- Current round commit/reveal data
- Lobby cache
- Node name

On startup:

- Load saved state if available.
- Ask user if they want to resume active duel.
- In mock mode, allow clearing state.

---

## 15. Mock Mode

Implement mock transport so the game can be tested without Meshtastic hardware.

Run:

```text
python -m duelmesh.cli --mock --node-name Alice
python -m duelmesh.cli --mock --node-name Bob
```

The mock mode may use:

- Local file queue
- Local UDP on localhost
- In-memory mock for tests

Prefer a simple local file or localhost approach for two terminal testing.

README must explain how to test two players locally.

---

## 16. Transport Layer

Create a transport abstraction.

Required classes:

```text
BaseTransport
MeshtasticTransport
MockTransport
```

Transport must support:

```text
send_public(packet)
send_direct(packet, destination_id)
start_listening(callback)
close()
```

MeshtasticTransport should:

- Connect to serial Meshtastic device
- Support optional `--port`
- Send discovery messages to selected channel index
- Send direct messages to opponent when destination ID exists
- Fall back gracefully if direct send fails
- Subscribe to incoming Meshtastic text messages
- Ignore non-DuelMesh packets

---

## 17. Testing Requirements

Provide pytest tests for:

- Damage calculation
- Block calculation
- Draw condition
- Win condition
- Numeric zone parsing
- Invalid choices
- Protocol encode/decode
- Compact packet validation
- Commit hash generation
- Commit-reveal verification
- Lobby expiration
- Two-player lock
- Duplicate packet ignore
- Mock transport send/receive
- ASCII UI output contains expected labels

---

## 18. README Requirements

README must include:

- What DuelMesh is
- Why it is designed for Meshtastic
- Installation
- Running in mock mode
- Running with a real Meshtastic node
- Meshtastic node configuration
- Creating the MeshGames channel
- Opening a game
- Joining a game
- Playing a duel
- How attack/defense works
- How commit-reveal prevents cheating
- How ACK/retry works
- Known limitations
- Troubleshooting
- Example full session

Include an example session:

```text
Alice:
python -m duelmesh.cli --mock --node-name Alice

/open

Bob:
python -m duelmesh.cli --mock --node-name Bob

/games
/join K7Q4
/duel
```

---

## 19. Quality Requirements

The code must be:

- Runnable
- Clear
- Modular
- Tested
- Simple
- Reliable
- Easy to extend

Do not return placeholders.

Do not say "implementation omitted".

Do not provide pseudocode.

Return the full codebase file by file.

---

## 20. Final Product Feel

The result should feel like:

```text
ChatWars-style duels
+ Meshtastic off-grid messaging
+ ASCII terminal gaming
+ reliable low-bandwidth protocol
```

The game should be fun, simple, and practical for real Meshtastic users.
