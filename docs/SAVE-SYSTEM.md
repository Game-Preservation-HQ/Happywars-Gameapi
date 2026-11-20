# Happy Wars save system

## What a save is

Happy Wars keeps a player's progress in one JSON object called `JsonSaveData`. Its `ID` is always `"SaveData000"`. It holds:

- Happy Stars and Happy Tickets
- campaign, mission and quest progress
- the character's look for each class and set
- every item the player owns, and what each class has equipped
- the career battle record
- a few menu and display options

The game gets this save from the game server every time it starts. After that the server keeps it up to date as the player plays (match results, missions, the spinner, item and look changes), and the next start downloads the new copy. The game never uploads the whole save itself.

Two PC builds read this format: the Steam Early Access build 0.5.2, which identifies itself as `Cores_EarlyAccess`, and build 1.63 (`Ver_1_63_0`). Both use the same member names, types and layouts.

Every example here is JSON in the exact form the game reads. The values come from a sample save the game loads, with example progress added where a section says so. A trimmed copy of the whole sample is near the end.

## How the game gets its save

At start-up the game makes three calls, in this order:

| Call | What it does |
| --- | --- |
| `UserExistence` | Asks whether the player has a save. The answer code `811` means there is none yet. |
| `CreateSaveData` | Only when there is none: makes a new save. |
| `CoreSaveDataLoad` | Downloads the save. |

Each call is a POST whose body is one line of `name:value` pairs. `f` names the call and `pid` is the player's Steam ID:

```
version:Cores_EarlyAccess,f:CoreSaveDataLoad,userid:(null),pid:<Steam ID>,xuid:DEBUG_CLIENT_XUID
```

### The answer

The answer to `CoreSaveDataLoad` is the save, packed in three steps:

1. The save goes inside an outer object: `{"JsonSaveData": {…}}`.
2. That JSON text is compressed with zlib (deflate with the 2-byte zlib header, the way Python's `zlib.compress` makes it).
3. The compressed bytes are written out as base64, and the base64 text goes between double quotes.

So the whole body is one quoted string. The sample's answer is 2,826 bytes and starts like this:

```
"eNrtXFFz4jgS/i9+zlxZkg0kbxdCJuwyEzZkLg9TU1MKCNDFtry2SYad4r9fS7KM7TOQk…
```

The game reads a `200` answer this way: it cuts the body at the first `_` if there is one, takes the text between the first and the last double quote, decodes the base64, inflates the result and reads its `JsonSaveData` member.

### Unpacking a save

```python
import base64, json, sys, zlib

raw = open(sys.argv[1], encoding='ascii').read().strip()
data = json.loads(zlib.decompress(base64.b64decode(raw.strip('"'))))
save = data['JsonSaveData']
print(save['ID'], save['mainData']['happyStar'], len(save['itemSeeds']))
```

On the sample answer this prints `SaveData000 12500 42`.

### Packing a save

```python
import base64, json, zlib

def pack(save):
    text = json.dumps({'JsonSaveData': save}, separators=(',', ':'))
    return '"' + base64.b64encode(zlib.compress(text.encode(), 9)).decode() + '"'
```

The game only reads the save at start-up. What the player does after that reaches the server through other calls (`GameResult`, `Mission`, `Spinner`, `ItemEnhance`, `ItemSynthesis`, `ItemEquip`, `CharaCustom`, `StyleSelect`, `TreasureMap`, `ReceiveDLC` and more), and the next `CoreSaveDataLoad` carries the result.

## The top level

`JsonSaveData` has 27 members. In the sample they come in this order. Members marked *keyed* are objects of `{"v": …}` values, explained under *Keyed maps and bit sets*. A dash means the meaning isn't known yet (see the last section).

| Member | Type | What it holds | Sample |
| --- | --- | --- | --- |
| `ID` | string | Always the same | `"SaveData000"` |
| `mainData` | object | Currency, tickets and progress | next section |
| `battleRecord` | object | Career totals | `{"values": {…}}` |
| `profiles` | object | The looks of the 9 class and set slots | `{"0": {…}, …}` |
| `itemSeeds` | object | Every item the player owns | `{"0": {"itemSeed": {…}}, …}` |
| `values` | list | — | `[]` |
| `blobResponse` | bool | — | `false` |
| `systemData` | object | Options | see *Options* |
| `isInGameModeHistory` | list of 256 `{"v": bool}` | One flag per game mode | `[{"v": false}, {"v": false}, {"v": true}, …]` |
| `lastProfileIndex` | int | — | `0` |
| `lastProfileSetIndex` | list of 3 ints | — | `[0, -1, -1]` |
| `itemFilterType` | int | The item list's filter | `0` |
| `totalHappyTimeCount` | int | — | `0` |
| `hotTimeDialogShowCount` | int | — | `0` |
| `isGetItemInResult` | bool | — | `false` |
| `isShowHighLeagueDialog` | bool | — | `false` |
| `isFavoriteStage` | list of 30 bools | One per stage | 30 × `true` |
| `lastSelectedStageKind` | int | — | `6` |
| `confirmedJobStyleDetail` | keyed bools | One per job style | `{"1": {"v": false}, "3": {"v": false}, "5": {"v": false}}` |
| `checkedCampaignHistory` | list of 64 `{"v": bool}` | One per campaign entry | `[{"v": false}, {"v": true}, …]` |
| `isCheckedCatalogPanel` | list of 128 `{"v": bool}` | One per catalog panel | 128 × `{"v": false}` |
| `catalogElementHistory` | list of 256 `{"v": int}` | Catalog history, `-1` for none | 256 × `{"v": -1}` |
| `catalogBargainHistory` | list of 8 `{"v": int}` | Bargain history, `-1` for none | 8 × `{"v": -1}` |
| `catalogLastSaleHistory` | list of 256 `{"v": int}` | Last-sale history, `-1` for none | 256 × `{"v": -1}` |
| `sentientTelemetryRecordingId` | int | — | `2147483647` |
| `lastUpdateInfomationVersion` | int | The game's spelling | `0` |
| `newItemUniqueId` | keyed ints | — | `{"20": {"v": 1}, "22": {"v": 1}}` |

The lists of `{"v": …}` must stay lists and the keyed members must stay objects. The game refuses a save where a member has the other shape.

## mainData

`mainData` has 59 members. Numbers are plain JSON integers unless the table says otherwise. The sample values are a fresh save's, with example progress in `happyStar`, `ticketUnlockedJobStyle` and `completedCampaignMission`.

### Currency and tickets

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `happyStar` | int | `12500` | Happy Stars, the in-game money |
| `presentTicketNum` | int | `20` | Happy Tickets given to the player |
| `useTicketNum` | int | `30` | Happy Tickets the player has spent |
| `happyCardPlayTicket` | int | `0` | Happy Card tickets |
| `happyCardStarTicket` | int | `0` | Happy Card tickets |
| `happyCardJobTicket` | int | `0` | Happy Card tickets |
| `boostSpawnTicket` | int | `0` | Boost spawn tickets |
| `loginBonusTicket` | int | `0` | Login bonus tickets |
| `ticketUnlockedJobStyle` | keyed bools | `{"3": {"v": true}}` | Job styles unlocked with a ticket |

Job styles are numbered class × 2 + variant (class 0 Warrior, 1 Cleric, 2 Mage), so style `3` is the Cleric's second style.

### Spinner

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `playSpinnerCount` | int | `42` | Spins played |
| `spinnerHappyPoint` | list | `[]` | — |
| `spinnerHappyPointDate` | list | `[]` | — |
| `spinnerHappyTimeCount` | int | `0` | — |

### Item customizing

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `itemCustomizeEnhanceCount` | list | `[]` | Enhance counts |
| `itemCustomizesynthesizeCount` | list | `[]` | Synthesis counts (the game's spelling) |
| `itemCustomizeLimitBreakCount` | int | `0` | Limit breaks done |
| `itemCustomizeLimitBreakCountByBuff` | int | `0` | Limit breaks done through buffs |

### League

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `lastRankLeague` | int | `0` | The last league rank |
| `leaguePoint` | **string** | `"0"` | League points, written as text |
| `leagueSeason` | int | `0` | — |
| `leagueSeasonId` | int | `0` | — |
| `leagueBonusPoint` | int | `0` | — |
| `leaguePenaltyPoint` | int | `0` | — |
| `lastLeaguePenaltyGetTime` | int | `0` | — |
| `lastLeagueLoginBonusGetTime` | int | `0` | — |
| `warResultHistory` | keyed ints | `{}` | — |
| `receivedLeagueSeasonBonusHistory` | keyed bools | `{}` | Season bonuses received |

### Presents and login bonus

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `lastPresentationDate` | int | `0` | — |
| `lastPrivatePresentationDate` | int | `0` | — |
| `loginBonusReceiveDate` | int | `0` | — |
| `loginBonusReceiveCount` | int | `0` | Login bonuses received |
| `receivedTitleLinkagePresentHistory` | keyed bools | `{}` | Title-linkage presents received |

### Special challenge

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `lastPlaySpecialChallengeIndex` | int | `0` | — |
| `specialChallengePointDate` | string | `""` | — |
| `specialChallengePointEasy` | int | `0` | Points on Easy |
| `specialChallengePointHard` | int | `0` | Points on Hard |
| `specialChallengeRewardSeedEasy` | string | `""` | — |
| `specialChallengeRewardSeedHard` | string | `""` | — |

### Campaign, missions and history

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `completedCampaignMission` | keyed bools | `{"0": {"v": true}, "1": {"v": true}, "8": {"v": true}}` | Campaign missions cleared, per difficulty |
| `achieveMissionFlag` | keyed bools | `{"10": {"v": true}}` | — |
| `historyMissionFlag` | keyed bools | `{"10": {"v": true}}` | — |
| `achieveQuestFlag` | keyed bools | `{}` | Quests achieved |
| `useSkillHistory` | keyed bools | `{}` | Skills used |
| `useGimmickHistory` | keyed bools | `{}` | Stage gimmicks used |
| `payUnlockedCampaignStory` | keyed bools | `{}` | Campaign stories unlocked by paying |

### Shop and catalog

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `itemShopBuyCount_Item` | int | `0` | Items bought |
| `itemShopBuyCount_FaceHair` | int | `0` | Faces and hair bought |
| `itemShopBuyCount_Bargain` | int | `0` | Bargains bought |
| `receivedItemShopFirstReward` | bool | `false` | The shop's first-purchase reward was given |
| `catalogBargainUpdateCount` | keyed ints | `{}` | — |
| `catalogBargainUpdateTimer` | keyed floats | `{}` | — |

### Items

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `isGetItemKind` | keyed bools | `{"1": {"v": true}, "2": {"v": true}, …}` | One bit per kind of item the player holds |
| `resetEquipmentItemUniqueIdCounter` | bool | `false` | — |

### Times and other

| Member | Type | Sample | Meaning |
| --- | --- | --- | --- |
| `timeStamp` | int | `0` | — |
| `lastDataLoadTime` | int | `0` | — |
| `lastGameStartTime` | int | `0` | — |
| `sentientContentsPermission` | list | `[]` | — |
| `sentientIsShowContentsPrice` | bool | `false` | — |
| `matchingResultWork` | string | `""` | — |

## Keyed maps and bit sets

Many members are *keyed maps*: a JSON object whose keys are decimal numbers written as text, and whose values are wrapped as `{"v": value}`.

```json
{"0": {"v": true}, "1": {"v": true}, "8": {"v": true}}
```

- **Keyed bools** are bit sets. Only the bits that are on are listed, and an empty set is `{}`.
- **Keyed ints** and **keyed floats** hold numbers, such as `{"2": {"v": 14}}` or `{"0": {"v": 1.5}}`.
- When the game loads a keyed map it looks each index up as text and sets that bit or value. An index that isn't in the map keeps the game's own value.

If you think of a bit set as a string of `0` and `1`, character *i* is bit *i*: `"110000001"` is the same set as the example above.

### Lists of `{"v"}` values

Some top-level members are full runs instead: a JSON list with one `{"v": …}` per index, such as `isInGameModeHistory` (256 entries) or `catalogElementHistory` (256 entries of `{"v": -1}`). Position *i* in the list is index *i*. These must stay lists, and keyed maps must stay objects.

### Campaign progress

`completedCampaignMission` has one bit per campaign, mission and difficulty:

```
bit = campaign × 64 + mission × 8 + difficulty
```

Campaigns and missions count from 0. Difficulty is 0 for Normal, 1 for Hard and 2 for Super Hard.

| Cleared | Bit |
| --- | --- |
| Campaign 1, mission 1, Normal | 0 × 64 + 0 × 8 + 0 = **0** |
| Campaign 1, mission 1, Hard | 0 × 64 + 0 × 8 + 1 = **1** |
| Campaign 1, mission 2, Normal | 0 × 64 + 1 × 8 + 0 = **8** |
| Campaign 2, mission 3, Super Hard | 1 × 64 + 2 × 8 + 2 = **82** |

A player who has cleared the first three rows has:

```json
"completedCampaignMission": {"0": {"v": true}, "1": {"v": true}, "8": {"v": true}}
```

### Other bit sets

- `ticketUnlockedJobStyle`: one bit per job style. With styles 3 and 5 unlocked it is `{"3": {"v": true}, "5": {"v": true}}`.
- `isGetItemKind`: one bit per item number (`ItemIndex`) in the game's item table, with room for 4,096. A player holding the Practice Sword (3), the Practice Hammer (4) and the Practice Staff (5) has bits 3, 4 and 5 on. The numbers are listed under *Items*.
- `achieveMissionFlag`, `historyMissionFlag`, `achieveQuestFlag`, `useSkillHistory`, `useGimmickHistory`, `payUnlockedCampaignStory`, `receivedLeagueSeasonBonusHistory` and `receivedTitleLinkagePresentHistory` have the same form. Their bit layouts are listed under *Not yet known*.

## Character looks (profiles)

`profiles` holds the look of each of the nine character slots: three classes with three sets each. It is an object keyed `"0"` to `"8"`:

```
key = class × 3 + set
```

Class 0 is the Warrior, 1 the Cleric and 2 the Mage. Sets count from 0, so the game's set 1 is 0 here.

| Keys | Class | Sets |
| --- | --- | --- |
| `"0"`, `"1"`, `"2"` | Warrior | 1, 2, 3 |
| `"3"`, `"4"`, `"5"` | Cleric | 1, 2, 3 |
| `"6"`, `"7"`, `"8"` | Mage | 1, 2, 3 |

Each slot has 13 integer members:

| Member | Meaning |
| --- | --- |
| `sexType` | 0 or 1 |
| `jobStyle` | The job style, class × 2 + variant |
| `personalityType` | Personality |
| `skinColor` | Skin colour number |
| `hairColor` | Hair colour number |
| `hairIndex` | Hair style number |
| `eyeIndex` | Eyes number |
| `mouthIndex` | Mouth number |
| `eyeOffsetType` | Eye offset |
| `mouthOffsetType` | Mouth offset |
| `baseKillingScore` | Killing score kept for this slot |
| `baseSupportScore` | Support score kept for this slot |
| `baseTacticsScore` | Tactics score kept for this slot |

The Warrior's and the Cleric's first sets in the sample, with example scores:

```json
"0": {"sexType": 0, "jobStyle": 0, "personalityType": 0, "skinColor": 3, "hairColor": 0, "hairIndex": 0, "eyeIndex": 2, "mouthIndex": 12, "eyeOffsetType": 0, "mouthOffsetType": 0, "baseKillingScore": 1840, "baseSupportScore": 960, "baseTacticsScore": 720},
"3": {"sexType": 0, "jobStyle": 2, "personalityType": 2, "skinColor": 0, "hairColor": 2, "hairIndex": 2, "eyeIndex": 5, "mouthIndex": 14, "eyeOffsetType": 0, "mouthOffsetType": 0, "baseKillingScore": 310, "baseSupportScore": 1250, "baseTacticsScore": 400}
```

### Starting looks

A slot that isn't in `profiles` keeps the game's own starting look. These are the starting looks; in each one `jobStyle` is class × 2 and both offsets are 0:

| Key | sexType | personalityType | skinColor | hairColor | hairIndex | eyeIndex | mouthIndex |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `"0"` | 0 | 0 | 3 | 0 | 0 | 2 | 12 |
| `"1"` | 0 | 0 | 1 | 1 | 1 | 0 | 0 |
| `"2"` | 1 | 0 | 0 | 2 | 6 | 15 | 18 |
| `"3"` | 0 | 2 | 0 | 2 | 2 | 5 | 14 |
| `"4"` | 0 | 2 | 3 | 0 | 1 | 9 | 2 |
| `"5"` | 1 | 2 | 1 | 1 | 7 | 18 | 15 |
| `"6"` | 1 | 0 | 1 | 1 | 4 | 11 | 17 |
| `"7"` | 0 | 0 | 0 | 2 | 3 | 3 | 11 |
| `"8"` | 0 | 0 | 3 | 0 | 5 | 4 | 16 |

### Scores

The three base scores are kept per slot. After a match, each class's killing, support and tactics scores are added to that class's first set (`"0"`, `"3"` or `"6"`). The medal rank the game shows comes from the totals over all nine slots.

## Items (itemSeeds)

`itemSeeds` lists every item the player owns. It is an object keyed `"0"`, `"1"`, `"2"` … in order, with room for 1,024 items. Each value wraps one record in `itemSeed`:

```json
"2": {"itemSeed": {"ID": "ITEM_WEPON_0000", "EquipProfileIndex": 0, "BaseRandomSeed": 0, "Level": 1, "New": true, "First": true, "BuffSlot": ["", "", "", ""], "LimitBreakCount": 0, "EquipmentPart": 2, "EnhanceExperience": 0, "UniqueID": 3}}
```

This is the Practice Sword, worn as the weapon by the Warrior's first set.

| Member | Type | Meaning |
| --- | --- | --- |
| `ID` | string | The item's name in the game's item table, such as `"ITEM_WEPON_0000"` |
| `EquipProfileIndex` | int | Which slot wears it, `-1` when none does (below) |
| `BaseRandomSeed` | int | — |
| `Level` | int | The item's level |
| `New` | bool | Marked as new in the item list |
| `First` | bool | — |
| `BuffSlot` | list of 4 strings | The item's buffs, `""` for an empty slot |
| `LimitBreakCount` | int | Limit breaks done on this item |
| `EquipmentPart` | int | Where it is worn (below), `0` when it isn't worn |
| `EnhanceExperience` | number | Enhance experience |
| `UniqueID` | int | The item's own number |

### Who wears an item

```
EquipProfileIndex = set × 65536 + class      that is, (set << 16) | class
```

Sets count from 0, and classes are 0 Warrior, 1 Cleric, 2 Mage.

| Worn by | EquipProfileIndex |
| --- | --- |
| Nobody | `-1` |
| Warrior, set 1 | `0` |
| Cleric, set 1 | `1` |
| Mage, set 1 | `2` |
| Warrior, set 2 | `65536` |
| Cleric, set 2 | `65537` |
| Mage, set 3 | `131074` |

| EquipmentPart | Part |
| --- | --- |
| `0` | Head |
| `1` | Armor |
| `2` | Weapon |
| `3` | Shield |
| `4` | Accessory |

Head is `0` too, so `EquipProfileIndex` `-1` is what marks an item as not worn.

In the sample, the first set of each class wears this (the `itemSeeds` key is in brackets):

| Slot | Weapon | Armor | Shield |
| --- | --- | --- | --- |
| Warrior, set 1 | Practice Sword (`"2"`) | Practice Armor (`"6"`) | Practice Shield (`"5"`) |
| Cleric, set 1 | Practice Hammer (`"3"`) | Practice Cloak (`"7"`) | Practice Shield (`"17"`) |
| Mage, set 1 | Practice Staff (`"4"`) | Practice Robe (`"8"`) | — |

### Item names

`ID` names an entry in the game's item table. Each entry also has a number, its `ItemIndex`, which is the bit it sets in `isGetItemKind`. The game spells weapons `WEPON`. The kinds of item in the sample:

| ID | Name | ItemIndex | Worn by |
| --- | --- | --- | --- |
| `ITEM_WEPON_NON_0000` | NakedSword\_1 | 1 | all |
| `ITEM_SHIELD_NON_0000` | NakedShield\_1 | 2 | all |
| `ITEM_WEPON_0000` | Practice Sword | 3 | Warrior |
| `ITEM_WEPON_0025` | Practice Hammer | 4 | Cleric |
| `ITEM_WEPON_0030` | Practice Staff | 5 | Mage |
| `ITEM_SHIELD_0000` | Practice Shield | 6 | Warrior, Cleric |
| `ITEM_ARMOR_0000` | Practice Armor | 10 | Warrior |
| `ITEM_ARMOR_0005` | Practice Cloak | 11 | Cleric |
| `ITEM_ARMOR_0010` | Practice Robe | 12 | Mage |
| `ITEM_WEPON_0045` | Soldier's Sword | 13 | Warrior |
| `ITEM_WEPON_0050` | Veteran's Sword | 14 | Warrior |
| `ITEM_WEPON_0055` | Hero's Sword | 15 | Warrior |

So the sample's `isGetItemKind` has bits 1 to 6 and 10 to 15 on.

## Battle record

`battleRecord` holds career totals in one keyed map, `values`, whose keys are names instead of numbers. With example numbers:

```json
"battleRecord": {"values": {"TotalGameWin01": {"v": 37}, "TotalKillByWarrior01": {"v": 212}, "TotalScore01": {"v": 48210}, "TotalPlayTime01": {"v": 61200}}}
```

Each name ends in a two-digit game mode number: `03` is skirmish and `04` is quick match. Names seen so far:

- `TotalScore01` to `TotalScore05`
- `TotalGameWin01`, `TotalGameWin05`
- `TotalKillByWarrior01`, `TotalKillByWarrior04`
- `TotalKillByMage01`
- `TotalHealByCleric01`
- `TotalPlayTime01`

The game reads every name and value in `values`, whatever the name, so the list above may not be complete.

## Options (systemData)

```json
"systemData": {
  "cameraReverse": false,
  "volumes": [0.7, 0.7, 0.7],
  "gammaUserLinear": 256,
  "powerColor": "POWER_COLOR_WHITE",
  "specificHudEnable": true,
  "contentPermission": {
    "permission": [{"v": 767}, {"v": 767}, {"v": 1048575}, {"v": 1048575}, {"v": 1048575}, {"v": 1048575},
                   {"v": 63}, {"v": 63}, {"v": 63}, {"v": 63}, {"v": 468}, {"v": 468}],
    "offerIds": [{"v": 0}, {"v": 0}, … 42 in all],
    "enableOfferIds": [{"v": false}, {"v": false}, … 42 in all]
  }
}
```

| Member | Type | Meaning |
| --- | --- | --- |
| `cameraReverse` | bool | Inverted camera |
| `volumes` | list of 3 numbers | Sound volumes, from 0 to 1 |
| `gammaUserLinear` | int | Brightness (gamma) |
| `powerColor` | string | A colour option, by name |
| `specificHudEnable` | bool | A HUD option |
| `contentPermission.permission` | list of 12 `{"v": int}` | — |
| `contentPermission.offerIds` | list of 42 `{"v": int}` | — |
| `contentPermission.enableOfferIds` | list of 42 `{"v": bool}` | — |

## A whole example

This is the sample save with its example progress, trimmed to fit: long lists show their first two entries and how many there are, and `profiles` and `itemSeeds` show two entries each. Because of the `…` lines it isn't valid JSON as shown. The full file is `docs/save-example.json` in the Happywars-Gameapi repository.

```
{"JsonSaveData": {
  "ID": "SaveData000",
  "mainData": {
    "timeStamp": 0,
    "lastDataLoadTime": 0,
    "lastGameStartTime": 0,
    "happyStar": 12500,
    "useTicketNum": 30,
    "presentTicketNum": 20,
    "happyCardPlayTicket": 0,
    "happyCardStarTicket": 0,
    "happyCardJobTicket": 0,
    "boostSpawnTicket": 0,
    "loginBonusTicket": 0,
    "ticketUnlockedJobStyle": {"3": {"v": true}},
    "lastPlaySpecialChallengeIndex": 0,
    "playSpinnerCount": 42,
    "spinnerHappyPoint": [],
    "spinnerHappyPointDate": [],
    "spinnerHappyTimeCount": 0,
    "itemCustomizeEnhanceCount": [],
    "itemCustomizesynthesizeCount": [],
    "itemCustomizeLimitBreakCount": 0,
    "itemCustomizeLimitBreakCountByBuff": 0,
    "lastRankLeague": 0,
    "leaguePoint": "0",
    "leagueSeason": 0,
    "leagueBonusPoint": 0,
    "leaguePenaltyPoint": 0,
    "lastLeaguePenaltyGetTime": 0,
    "lastLeagueLoginBonusGetTime": 0,
    "leagueSeasonId": 0,
    "warResultHistory": {},
    "receivedLeagueSeasonBonusHistory": {},
    "receivedTitleLinkagePresentHistory": {},
    "lastPresentationDate": 0,
    "lastPrivatePresentationDate": 0,
    "loginBonusReceiveDate": 0,
    "loginBonusReceiveCount": 0,
    "specialChallengePointDate": "",
    "specialChallengePointEasy": 0,
    "specialChallengePointHard": 0,
    "specialChallengeRewardSeedEasy": "",
    "specialChallengeRewardSeedHard": "",
    "completedCampaignMission": {"0": {"v": true}, "1": {"v": true}, "8": {"v": true}},
    "achieveMissionFlag": {"10": {"v": true}},
    "historyMissionFlag": {"10": {"v": true}},
    "achieveQuestFlag": {},
    "useSkillHistory": {},
    "useGimmickHistory": {},
    "payUnlockedCampaignStory": {},
    "catalogBargainUpdateCount": {},
    "catalogBargainUpdateTimer": {},
    "itemShopBuyCount_Item": 0,
    "itemShopBuyCount_FaceHair": 0,
    "itemShopBuyCount_Bargain": 0,
    "receivedItemShopFirstReward": false,
    "isGetItemKind": {"1": {"v": true}, "2": {"v": true}, "3": {"v": true}, "4": {"v": true}, "5": {"v": true}, "6": {"v": true}, "10": {"v": true}, "11": {"v": true}, "12": {"v": true}, "13": {"v": true}, "14": {"v": true}, "15": {"v": true}},
    "sentientContentsPermission": [],
    "sentientIsShowContentsPrice": false,
    "matchingResultWork": "",
    "resetEquipmentItemUniqueIdCounter": false
  },
  "battleRecord": {"values": {"TotalGameWin01": {"v": 37}, "TotalKillByWarrior01": {"v": 212}, "TotalScore01": {"v": 48210}, "TotalPlayTime01": {"v": 61200}}},
  "profiles": {
    "0": {"sexType": 0, "jobStyle": 0, "personalityType": 0, "skinColor": 3, "hairColor": 0, "hairIndex": 0, "eyeIndex": 2, "mouthIndex": 12, "eyeOffsetType": 0, "mouthOffsetType": 0, "baseKillingScore": 1840, "baseSupportScore": 960, "baseTacticsScore": 720},
    "3": {"sexType": 0, "jobStyle": 2, "personalityType": 2, "skinColor": 0, "hairColor": 2, "hairIndex": 2, "eyeIndex": 5, "mouthIndex": 14, "eyeOffsetType": 0, "mouthOffsetType": 0, "baseKillingScore": 310, "baseSupportScore": 1250, "baseTacticsScore": 400},
    … 9 in all
  },
  "itemSeeds": {
    "0": {"itemSeed": {"ID": "ITEM_WEPON_NON_0000", "EquipProfileIndex": -1, "BaseRandomSeed": 0, "Level": 1, "New": true, "First": true, "BuffSlot": ["", "", "", ""], "LimitBreakCount": 0, "EquipmentPart": 0, "EnhanceExperience": 0, "UniqueID": 1}},
    "2": {"itemSeed": {"ID": "ITEM_WEPON_0000", "EquipProfileIndex": 0, "BaseRandomSeed": 0, "Level": 1, "New": true, "First": true, "BuffSlot": ["", "", "", ""], "LimitBreakCount": 0, "EquipmentPart": 2, "EnhanceExperience": 0, "UniqueID": 3}},
    … 42 in all
  },
  "values": [],
  "blobResponse": false,
  "systemData": {"cameraReverse": false, "volumes": [0.7, 0.7, 0.7], "gammaUserLinear": 256, "powerColor": "POWER_COLOR_WHITE", "specificHudEnable": true, "contentPermission": {"permission": [{"v": 767}, {"v": 767}, … 12 in all], "offerIds": [{"v": 0}, {"v": 0}, … 42 in all], "enableOfferIds": [{"v": false}, {"v": false}, … 42 in all]}},
  "isInGameModeHistory": [{"v": false}, {"v": false}, … 256 in all],
  "lastProfileIndex": 0,
  "lastProfileSetIndex": [0, -1, -1],
  "itemFilterType": 0,
  "totalHappyTimeCount": 0,
  "hotTimeDialogShowCount": 0,
  "isGetItemInResult": false,
  "isShowHighLeagueDialog": false,
  "isFavoriteStage": [true, true, … 30 in all],
  "lastSelectedStageKind": 6,
  "confirmedJobStyleDetail": {"1": {"v": false}, "3": {"v": false}, "5": {"v": false}},
  "checkedCampaignHistory": [{"v": false}, {"v": true}, … 64 in all],
  "isCheckedCatalogPanel": [{"v": false}, {"v": false}, … 128 in all],
  "catalogElementHistory": [{"v": -1}, {"v": -1}, … 256 in all],
  "catalogBargainHistory": [{"v": -1}, {"v": -1}, … 8 in all],
  "catalogLastSaleHistory": [{"v": -1}, {"v": -1}, … 256 in all],
  "sentientTelemetryRecordingId": 2147483647,
  "lastUpdateInfomationVersion": 0,
  "newItemUniqueId": {"20": {"v": 1}, "22": {"v": 1}}
}}
```

## Not yet known

These still need tracing in the game:

- `values` and `blobResponse` at the top level.
- `lastProfileIndex` and `lastProfileSetIndex`.
- Which `sexType` value is which.
- What each place in `isInGameModeHistory` (256) and `checkedCampaignHistory` (64) stands for.
- The bit layouts of `achieveMissionFlag`, `historyMissionFlag`, `achieveQuestFlag`, `useSkillHistory`, `useGimmickHistory`, `payUnlockedCampaignStory`, `receivedLeagueSeasonBonusHistory` and `receivedTitleLinkagePresentHistory`.
- What `warResultHistory`, `catalogBargainUpdateCount` and `catalogBargainUpdateTimer` count, and what the catalog lists hold.
- The units of the time and date members (`timeStamp`, `lastDataLoadTime`, `lastGameStartTime`, `lastPresentationDate`, `loginBonusReceiveDate`, the league times) and the form of `specialChallengePointDate`.
- How `presentTicketNum` and `useTicketNum` combine with bought tickets into the balance the game shows.
- `BaseRandomSeed` and `First` in an item record, and `newItemUniqueId`.
- The battle record's suffixes `01`, `02` and `05`, and the unit of `TotalPlayTime`.
- The order of the three `volumes`, and what the `contentPermission` numbers mean.
- The `sentient…` members and `matchingResultWork`.

Written by Serenity, Game Preservation HQ.
