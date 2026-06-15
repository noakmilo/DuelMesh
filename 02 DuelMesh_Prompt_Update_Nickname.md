# DuelMesh Prompt Update

Add the following section to the DuelMesh Codex prompt:

## PLAYER IDENTITY SYSTEM

DuelMesh must support player nicknames.

On first launch:

- Ask the user to choose a nickname.
- Store it locally.
- Reuse it on future launches.
- Allow changing it later with:

/nick NEWNAME

Nickname requirements:

- Minimum length: 3 characters
- Maximum length: 12 characters
- Allowed characters:
  - A-Z
  - a-z
  - 0-9
  - underscore (_)
  - dash (-)

Reject:
- spaces
- emojis
- control characters
- punctuation outside _ and -

Examples:

Valid:
Camilo
Noa87
DXSentinel
Ham_01
LoRa-King

Invalid:
Camilo Noa
🔥Ham🔥
VeryLongNickname12345

Default nickname:
- Use Meshtastic long name if available.
- If unavailable, prompt the user to create one.

Display:

Nickname: Camilo
Node ID: !a1b2c3d4

Game listings should show both nickname and node ID.

Example:

╔══════════════════════════════════════╗
║              OPEN GAMES              ║
╠══════════════════════════════════════╣
║ K7Q4  Camilo      !a1b2c3d4 Waiting  ║
║ M2LP  Alice       !f7e8d9c0 Waiting  ║
╚══════════════════════════════════════╝

Protocol:

Every packet should contain:

"n":"Camilo"

Example:

{
  "a":"dm",
  "v":1,
  "t":"offer",
  "g":"K7Q4",
  "n":"Camilo",
  "s":"!a1b2c3d4",
  "m":"abc123",
  "ts":1710000000
}

For bandwidth efficiency:

- Nicknames must never exceed 12 characters.
- Protocol validation must reject longer nicknames.
- Nicknames are informational only.
- Node ID remains the authoritative identifier.

Additional commands:

/nick NEWNAME
/profile

/profile should display:

- Nickname
- Node ID
- Games played
- Wins
- Losses
- Draws

Store player profile locally.
