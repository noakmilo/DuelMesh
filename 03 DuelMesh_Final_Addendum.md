# DuelMesh Final Addendum

## PLAYER IDENTITY SYSTEM

- Nicknames required.
- 3-12 characters.
- Allowed: A-Z, a-z, 0-9, _ and -
- Stored locally.
- Change with /nick NEWNAME.
- Default to Meshtastic long name if available.

Reserved nicknames:
- SYSTEM
- ADMIN
- SERVER
- DUELMESH
- MESHGAMES

Commands:
- /nick NEWNAME
- /profile

Profile fields:
- Nickname
- Node ID
- Games Played
- Wins
- Losses
- Draws

Nicknames are informational only.
Node ID remains authoritative.

---

## FUTURE CLASS SYSTEM (DISABLED IN V1)

IMPORTANT:
The class system is NOT active in Version 1.

Design the architecture so classes can be enabled in V2 without major refactoring.

All players use identical stats in V1.

Future classes:

### Knight
Base HP: 12
Passive: +2 starting HP

### Sniper
Base HP: 10
Passive: Head attacks deal +0.5 damage

### Guardian
Base HP: 11
Passive: Chance to negate all damage after successful defense

### Medic
Base HP: 10
Passive: Regenerate 0.5 HP every 3 rounds

### Scout
Base HP: 9
Passive: Wins initiative ties

### Berserker
Base HP: 10
Passive: Gains +0.5 damage below 3 HP

Future commands:
- /class
- /classes

Future progression:
- XP
- Levels
- Achievements
- Seasonal ladders
- Guilds
- Tournaments

Version 1 protocol must ignore class data.

Future protocol example:
{
  "class":"knight"
}
