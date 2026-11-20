# Happy Wars game API

This page covers the calls the Steam game (HappyWars.exe 1.63) and its launcher make to the revival servers, and the reply each one expects. It has two parts:

- **The Pollux calls:** account, save, login, equipment, Spinner and match calls.
- **The purchase calls** behind the "Get Happy Tickets" shop: HappyTicketAsset, HappyTicketSum, InitTxn and FinalizeTxn.

The save-data layout inside `JsonSaveData` has its own document, [SAVE-SYSTEM.md](SAVE-SYSTEM.md). This page only shows how the save travels.

Every example below is a real reply from the server, run with a made-up player (Steam id `76561190000000001`). Long values are sometimes shortened.

---

## 1. General rules

### 1.1 Transport

| Use | Method and path | Body | Reply |
|---|---|---|---|
| Game and launcher calls ("Pollux") | `POST /api/pollux/` (also `/api/pollux`) | Pollux text, see 1.2 | see 1.4 |
| Purchase calls | `POST /api/<Function>` on the purchase server: `/api/HappyTicketAsset`, `/api/HappyTicketSum`, `/api/InitTxn`, `/api/FinalizeTxn` | plain JSON | quoted JSON |

- Any other method on `/api/pollux/` gets `405 {"status":"error","error":"Method not allowed"}`.
- The identity headers are:
  - `X-Identifier`: the Steam id.
  - `P-Authorization`: the Steam session ticket as text.

### 1.2 Request body

The server checks the first characters of the raw body to pick a format:

1. **JSON** when the body starts with `{` or `[`, for example `{"f":"MapVote","pid":"...",...}`. The purchase calls and MapVote use JSON.
2. **k=v form** when it has `=` and no `:`, split on `&` or `,`.
3. **Pollux classic** otherwise: `key:value,key:value,...` with no spaces and no quoting. The game uses this for every Pollux call, for example:
   `version:Ver_1_63_0,f:TitleLogin,pid:76561190000000001`

The keys every Pollux call carries:

| Key | Type | Meaning |
|---|---|---|
| `f` | string | The function name, case-insensitive. Old names are accepted as aliases: `CoreSaveDataCreate` means CreateSaveData, and `CoreSaveDataRestart` and `CoreSaveDataDelete` mean RestartSaveData. |
| `pid` | string (Steam id, 17 digits) | The player. |
| `version` | string | The client build: `Ver_1_63_0` for the Steam game, and `Cores_EarlyAccess` from the launcher account calls. The server does not change its replies by version. |
| `userid` | `(null)` or number | Sent as `(null)` by CoreSaveDataLoad; the server fills it from `pid`. |

### 1.3 Field names and values

- **Key names:** the server keeps only `A-Z a-z 0-9 _` in a key. It turns `snake_case` into `camelCase` only where an underscore comes before a lower-case letter.
  - `open_style_index` becomes `openStyleIndex`.
  - `material_0` and `selectedBuff_0` stay as they are.
  - The server accepts both spellings, so this page lists the names the game sends.
- **Values:**
  - `(null)` means null.
  - `true` and `false` are booleans.
  - A run of digits is an integer, with three exceptions that stay strings: ids (`pid`, `steamid`, `xuid` and similar), the mission `history`, and values with a leading zero or more than 18 digits.
  - Anything else is a string.
- **Player id:** the server takes the player from the first of these that holds 8 to 20 digits: `pid`, `steamId`, `steamID`, the `X-Identifier` header, `X-SteamId`, `X-Steam-Id`, `userid`, `userId`.

### 1.4 Reply envelope

There are four reply forms:

| Form | Used by | What is on the wire |
|---|---|---|
| **Quoted JSON** | almost every game call, and the purchase calls | `"` + JSON + `"`. The JSON inside is **not** escaped: the body really is `"{"JsonRadarResultTitleLogin":{...}}"`. The client strips the outer quotes and parses the rest. |
| **Quoted base64 zlib** | CoreSaveDataLoad | `"` + base64(zlib(JSON, level 9)) + `"`. Inside is `{"JsonSaveData":{...}}`. The client only takes the save in this form; plain JSON is not applied. |
| **Plain base64 zlib text** | UserExistence, CreateSaveData, RestartSaveData (launcher) | base64(zlib("UserID:<a>_<b>")), with no quotes and `Content-Type: text/plain`. Before zlib the text is always `UserID:<n>_<m>`. The client splits on `_`, so a bare `UserID:<n>` must never be sent. A failure sends `UserID:0_0`. |
| **Plain JSON** | errors, MapVote | normal JSON without the outer quotes. |

Content types:

- Game calls: `application/json`, even though the body is quoted.
- Launcher account calls: `text/plain; charset=UTF-8`.
- Purchase calls: `text/html; charset=UTF-8`.
- Errors and MapVote: `application/json`.

JSON numbers keep their type:

- A float field such as `friendBonusScoreRate` or `EnhanceExperience` is sent as `1.0` or `0.0`, never `1`. The client reads it as a float.
- A sparse map keyed by small numbers (`{"0":{...},"3":{...}}`) is always an object, never a JSON array.

### 1.5 Wrapper families

Every JSON reply has one top-level key, the **wrapper**, that names the reply type. The client looks the wrapper up by its exact name.

| Family | Calls |
|---|---|
| `JsonRadarResult<Name>` | TitleLogin, GameResult, Mission, Spinner, ItemEquip, CharaCustom, StyleSelect, LoadingGameStart, LoadingGameEnd, ReceiveDLC, TreasureMap, UploadTelemetry |
| `RadarJsonResult<Name>` (the words swapped) | ItemEnhance, ItemSynthesis, RecordMatching, and the purchase calls: HappyTicketAsset, `BoughtTicketNum` (the reply to HappyTicketSum), InitTxn, FinalizeTxn |
| `JsonSaveData` | CoreSaveDataLoad |
| none | MapVote, errors, launcher account calls |

The Steam 1.63 HappyWars.exe holds each of those wrapper strings exactly once, apart from three:

- `JsonRadarResultUploadTelemetry` has 0 hits. The game does not bind that reply, so only the HTTP status matters.
- `JsonRadarResultItemEnhance` and `JsonRadarResultRecordMatching` have 0 hits. The server sends ItemEnhance and ItemSynthesis under both spellings; only the `RadarJsonResult` copy is read.

### 1.6 The inner `result`

The inner `result` takes one of three forms:

- **Status object:** `"result":{"funcResult":1,"lastStatus":0}` is success. Most game calls use it.
- **String `"OK"`:** LoadingGameStart and LoadingGameEnd send `"result":"OK"`.
- **Purchase form:** the purchase calls send `"result":"OK"` or `"result":"Failure"`. A failure adds an error object (section 6).

### 1.7 Missing keys and order

- The client binds reply fields by name. Field order does not matter, and a missing field keeps its default (0, false, empty).
- Types do matter: an int where the client wants a float, or an object where it wants a list, breaks the bind.
- A missing wrapper, or a reply that is not quoted as in 1.4, shows a network error in the game.

### 1.8 Shared shapes

**Item seed:** one item, used wherever a reply holds items (`itemSeed`, `rewardItem`, `receiveItemSeed`, `enhanceResultItemSeed` and so on).

| Field | Type | Meaning |
|---|---|---|
| `ID` | string | Item kind, e.g. `ITEM_WEPON_0570` (the game's own spelling). `ITEM_WEPON_NON_0000` with `UniqueID` 0 means an empty slot. |
| `UniqueID` | int | The player's id for this copy (0 = none). |
| `Level` | int | Item level. |
| `EnhanceExperience` | **float** | Progress to the next level. |
| `EquipmentPart` | int | Equipment part. |
| `LimitBreakCount` | int | Limit breaks done. |
| `BuffSlot` | list of 4 strings | Buff ids such as `Buff_AttackUp_00`, with `""` for an empty slot. An empty-slot item sends `0`. |
| `BaseRandomSeed` | int | Random seed. |
| `EquipProfileIndex` | int | The profile it is equipped on, or -1. |
| `First` | bool | First time obtained. |
| `New` | bool | Shows the "new" mark. |

**Currency totals** come back after most calls that change currency:

| Reply key | Save field | Meaning |
|---|---|---|
| `totalHappyStarNum` | `happyStar` | Happy Stars. GameResult spells this key `totalHppyStarNum`; the client wants that spelling there. |
| `totalHappyTicketNum` | `presentTicketNum` | Happy Tickets given. |
| `totalHappyTicketUseNum` | `useTicketNum` | Happy Tickets spent. The shown balance is given + bought (HappyTicketSum) − spent, capped at 999. |
| `totalHappyCardTicketNum` | `happyCardPlayTicket` | Happy Card play tickets. |
| `totalHappyCardStarTicketNum` | `happyCardStarTicket` | Happy Card star tickets. |
| `totalJobTypeTicketNum` | `happyCardJobTicket` | `[warrior, cleric, mage]` job tickets. |
| `totalBoostSpawnTicketNum` | `boostSpawnTicket` | Boost-spawn tickets. |
| `totalLoginBonusTicketNum` | `loginBonusTicket` | Login-bonus tickets. |

### 1.9 Error replies

All errors are plain JSON with `"status":"error"`, unless the table says otherwise.

| HTTP | Body | When |
|---|---|---|
| 400 | text `Error: Steam ID missing` | Launcher account call without a player |
| 401 | text `Error: Invalid authentication` | Launcher account call without a valid `P-Authorization` |
| 403 | `{"status":"error","error":"Function not allowed or missing"}` | Unknown or missing `f` |
| 404 | `Function handler '<f>' not implemented` | `f` is allowed but has no handler |
| 405 | `{"status":"error","error":"Method not allowed"}` | An unsupported method |
| 500 | `{"status":"error","error":"save_unreadable"}` or `save_write_failed` | Storage problem |
| 503 | `{"status":"error","error":"busy"}`, `Retry-After: 2` | Another request for the same player holds the save |
| 503 | `{"status":"error","error":"maintenance","message":"..."}`, `Retry-After: 3600` | Maintenance mode |

The launcher account calls also use the game's own result codes as HTTP statuses: 811, 812 and 802 (section 2).

### 1.10 Call order

1. **Launcher:** UserExistence. On 811 it sends CreateSaveData.
2. **Game start:** CoreSaveDataLoad → TitleLogin → HappyTicketSum → TreasureMap (daily) → ReceiveDLC.
3. **Menus:** CharaCustom, StyleSelect, ItemEquip, ItemEnhance, ItemSynthesis, Spinner, Mission. Shop: HappyTicketAsset → InitTxn → FinalizeTxn → HappyTicketSum.
4. **Match:** RecordMatching (and MapVote from the launcher DLL in a Quick Match lobby) → LoadingGameStart → LoadingGameEnd → GameResult. UploadTelemetry can come at any time.

---

## 2. Account calls (launcher)

These three replies are **plain base64 zlib text** (1.4). In each table, "Body before zlib" is the text inside the reply.

### 2.1 UserExistence

- **Path:** `POST /api/pollux/`
- **When:** the launcher starts, to see whether the Steam account has a save.

**Request:** headers `X-Identifier: <steam id>` and `P-Authorization: <Steam session ticket>`. Body:

`version:Cores_EarlyAccess,pid:<steam id>,f:UserExistence`

**Reply:**

| HTTP | Body before zlib | Meaning |
|---|---|---|
| 200 | `UserID:<a>_<b>` | The account exists. `<a>_<b>` is the server account id. |
| 811 | `UserID:0_0` | No account (the game's "no data in user DB"). The launcher then calls CreateSaveData. |
| 400 / 401 | text error | See 1.9. |
| 500 | `UserID:0_0` | Server error. |

**Example:**

```
POST /api/pollux/
version:Cores_EarlyAccess,pid:76561190000000001,f:UserExistence
→ 811  eNoLLU4t8nSxMog3AAATHQMm                 (unzips to UserID:0_0)
→ 200  eNoLLU4t8nSxMow3NLc0NbQ0NzU3BAA5EAUL     (after CreateSaveData; unzips to UserID:1_1795197571)
```

### 2.2 CreateSaveData

- **Path:** `POST /api/pollux/`. The `f` alias `CoreSaveDataCreate` also works.
- **When:** UserExistence answered 811.

**Request:** the same headers as UserExistence. Body:

`version:Cores_EarlyAccess,pid:<steam id>,f:CreateSaveData`

**Reply:**

| HTTP | Body before zlib | Meaning |
|---|---|---|
| 200 | `UserID:<a>_<b>` | Account and an empty save created. |
| 812 | `UserID:<a>_<b>` | It already existed. The id is still sent. |
| 802 | `UserID:0_0` | The save could not be written. |

**Example:** `200 → UserID:1_1795197571`, then the same request again gives `812 → UserID:1_1795197571`.

### 2.3 RestartSaveData

- **Path:** `POST /api/pollux/`. The aliases `CoreSaveDataRestart` and `CoreSaveDataDelete` also work.
- **When:** the player chooses to start over. The save is reset.

**Request:** `version:Cores_EarlyAccess,pid:<steam id>,f:RestartSaveData`, with the same headers.

**Reply:**

| HTTP | Body before zlib | Meaning |
|---|---|---|
| 200 | `UserID:<a>_<b>` | Done. |
| 811 | `UserID:0_0` | No account. |
| 802 | `UserID:0_0` | Failed. |

**Example:** `200 → UserID:1_1795197571`.

---

## 3. Save and login calls

### 3.1 CoreSaveDataLoad

- **Path:** `POST /api/pollux/`
- **When:** first thing after the game starts, and again after a relog.

**Request:** Pollux classic.

| Key | Type | Meaning |
|---|---|---|
| `version` | string | The client build |
| `f` | `CoreSaveDataLoad` | |
| `userid` | `(null)` | Always `(null)` from the client |
| `pid` | string | Steam id |

**Reply:** quoted base64 zlib (1.4). Inside is one wrapper, `JsonSaveData`, holding the whole save:

- `ID`: string, e.g. `SaveData000`.
- The main blocks: `systemData`, `mainData` (currency, tickets, flags; about 60 keys), `battleRecord`, `profiles`, `itemSeeds`, `values`, `blobResponse`.
- Flat menu-state keys: `lastProfileIndex`, `lastProfileSetIndex`, `isFavoriteStage`, `catalog*History` and others.
- `userid`: the Steam id as a **string**.

Nesting rules the client depends on:

- `profiles` is an object keyed by `class*3 + set` as a string (`"0"`, `"3"`, `"6"` and so on), not a list.
- `itemSeeds` is an object keyed `"0"`, `"1"` and so on (up to 1024 entries). Each entry is `{"itemSeed": <item seed>}`.
- Bool, int and float bit-maps are objects of `{"<index>":{"v":<value>}}`, e.g. `warResultHistory`, `catalogBargainUpdateCount` and the per-index unlock flags.
- `battleRecord` is `{"values":{"TotalScore04":{"v":<n>}, ...}}`.

All save fields are described in the save-data document.

**Example (start of the body only):**

```
POST /api/pollux/
version:Ver_1_63_0,f:CoreSaveDataLoad,userid:(null),pid:76561190000000001
→ 200 "eNrtXFtX2zgQ/i9+Tnts58LlrYRA0gZIY1geOByOsJVEG1vyyjI028N/35F..."
   unzipped: {"JsonSaveData":{"ID":"SaveData000","mainData":{"timeStamp":...,"happyStar":...,
              "useTicketNum":30,"presentTicketNum":20,...},"profiles":{"0":{...},"3":{...},"6":{...}},
              "itemSeeds":{"0":{"itemSeed":{...}},"1":{...}},...,"userid":"76561190000000001"}}
```

### 3.2 TitleLogin

- **Path:** `POST /api/pollux/`
- **When:** right after CoreSaveDataLoad, on the title screen.

**Request:** `version:Ver_1_63_0,f:TitleLogin,pid:<steam id>`. No other fields are read.

**Reply:** wrapper `JsonRadarResultTitleLogin`, flat: every field sits directly under the wrapper.

| Field | Type | Meaning |
|---|---|---|
| `totalHappyStarNum` … `totalLoginBonusTicketNum` | int / int[3] | Currency totals, as in 1.8 (all eight). |
| `rewardItemSeed` | list of item seeds | Items given at login (usually `[]`). |
| `presentationSuccess` | list | Presents delivered. |
| `presentationFailed` | string | Failure text, or `""`. |
| `presentationFailedResult` | list | |
| `receivedTitleLinkagePresent` | list | Title-linkage (DLC) presents received. |
| `presentReceiveLastDate`, `privatePresentReceiveLastDate` | int | Last present dates (0 = never). |
| `preLeagueSeasonRankingNo`, `preLeagueSeasonRankingUserNum` | int | The previous league season's rank and player count. |
| `rankLeagueSeasonId`, `rankLeaguePoint`, `lastRankLeague`, `saveRankLeagueSeasonId`, `bonusRankLeaguePoint` | int | League state. |
| `newRankLeagueSeason` | bool | Shows the new-season dialog. Keep it `false` unless a season really changed, or the dialog shows every login. |
| `receiveRankLeagueSeasonReward` | bool | A season reward is waiting. |
| `isExistUpdateSaveData` | bool | `true`: the save has updates. |
| `receivedLeagueRankingReward` | string | |
| `receivedLeagueRankingRewardResult` | list | |
| `userid` | number | The Steam id as a JSON number. |
| `now_league_point`, `pre_league_point`, `pre_league_rank_no`, `pre_season_user_num` | int | League info, in snake_case. |
| `result` | object | `{"funcResult":1,"lastStatus":0}` |

**Example:**

```
POST /api/pollux/
version:Ver_1_63_0,f:TitleLogin,pid:76561190000000001
→ 200 "{"JsonRadarResultTitleLogin":{"totalHappyStarNum":990099,"totalHappyTicketNum":20,
  "totalHappyTicketUseNum":30,"totalHappyCardTicketNum":0,"totalHappyCardStarTicketNum":1,
  "totalJobTypeTicketNum":[1,1,1],"totalBoostSpawnTicketNum":0,"totalLoginBonusTicketNum":0,
  "rewardItemSeed":[],"presentationSuccess":[],"presentationFailed":"","presentationFailedResult":[],
  "receivedTitleLinkagePresent":[],"presentReceiveLastDate":0,"privatePresentReceiveLastDate":0,
  "preLeagueSeasonRankingNo":0,"preLeagueSeasonRankingUserNum":0,"rankLeagueSeasonId":0,
  "rankLeaguePoint":0,"lastRankLeague":0,"saveRankLeagueSeasonId":0,"bonusRankLeaguePoint":0,
  "newRankLeagueSeason":false,"receiveRankLeagueSeasonReward":false,"isExistUpdateSaveData":true,
  "receivedLeagueRankingReward":"","receivedLeagueRankingRewardResult":[],"userid":76561190000000001,
  "now_league_point":0,"pre_league_point":0,"pre_league_rank_no":0,"pre_season_user_num":0,
  "result":{"funcResult":1,"lastStatus":0}}}"
```

### 3.3 TreasureMap (daily login bonus)

- **Path:** `POST /api/pollux/`
- **When:** after TitleLogin, when the game's login-bonus calendar has a row for this month.

**Request:** `version:Ver_1_63_0,f:TreasureMap,pid:<steam id>`. Only the player.

**Reply:** wrapper `JsonRadarResultTreasureMap`, flat.

| Field | Type | Meaning |
|---|---|---|
| `isAlreadyReceived` | bool | `true`: today's reward was already taken; nothing was given. |
| `isItemInventoryMax` | bool | The inventory is full. |
| `totalHappyStarNum` | int | Stars after the reward. |
| `receiveCount` | int | Reward days this month (1-31). Picks the calendar's `Day_NN`. Starts again each month. |
| `receiveDate` | int | `YYYYMMDD` of the claim. |
| `receiveHappyStar` | int | Stars given now (0 when already received). |
| `receiveItemSeed` | list of item seeds | Items given now. |
| `bonusDetailKey` | string | The calendar entry, e.g. `Star_1`. |
| `result` | object | Status object |

**Example:**

```
POST /api/pollux/
version:Ver_1_63_0,f:TreasureMap,pid:76561190000000001
→ 200 "{"JsonRadarResultTreasureMap":{"isAlreadyReceived":false,"isItemInventoryMax":false,
  "totalHappyStarNum":990007,"receiveCount":1,"receiveDate":20261120,"receiveHappyStar":800,
  "receiveItemSeed":[],"bonusDetailKey":"Star_1","result":{"funcResult":1,"lastStatus":0}}}"
  (the same day again: "isAlreadyReceived":true,...,"receiveHappyStar":0,...)
```

### 3.4 ReceiveDLC

- **Path:** `POST /api/pollux/`
- **When:** at login, to collect DLC and title-linkage presents.

**Request:** `version:Ver_1_63_0,f:ReceiveDLC,pid:<steam id>`.

**Reply:** wrapper `JsonRadarResultReceiveDLC`.

| Field | Type | Meaning |
|---|---|---|
| `dlcReceiveMessageId` | list of strings | Ids of the DLC present messages delivered. `[]` when there are none. The server remembers them so each is given once. |
| `result` | object | Status object |

**Example:** `→ 200 "{"JsonRadarResultReceiveDLC":{"dlcReceiveMessageId":[],"result":{"funcResult":1,"lastStatus":0}}}"`

---

## 4. Character and item calls

### 4.1 CharaCustom

- **Path:** `POST /api/pollux/`
- **When:** the player saves the character look.

**Request:** Pollux classic. All values are int.

| Key | Meaning |
|---|---|
| `set_index` | The Dress-Up set being edited: 0, 1 or 2 (for example Warrior1, Warrior2, Warrior3) |
| `user_index` | Optional. Names the slot directly and wins over `set_index` (the example below sends it) |
| `userid` | `(null)`. The player account, never a slot. |
| `job_index` | 0 warrior, 1 cleric, 2 mage |
| `hair_index`, `eye_index`, `eye_offset`, `mouth_index`, `mouth_offset` | Face parts |
| `skin_color`, `hair_color` | Colors |
| `sex_type` | Body type |
| `personality_type` | Voice and personality |

**Reply:** wrapper `JsonRadarResultCharaCustom`, which echoes the saved look.

- `userIndex`: int, always 0.
- `jobIndex`, `setIndex`, `hairIndex`, `eyeIndex`, `eyeOffset`, `mouthIndex`, `mouthOffset`, `skinColor`, `hairColor`, `sexType`, `personalityType`: int.
- `isWriteData`: bool, `true`.
- `result`: the status object.

**Example:**

```
version:Ver_1_63_0,f:CharaCustom,pid:76561190000000001,user_index:0,job_index:0,hair_index:2,eye_index:1,
eye_offset:0,mouth_index:3,mouth_offset:0,skin_color:1,hair_color:4,sex_type:0,personality_type:1
→ 200 "{"JsonRadarResultCharaCustom":{"userIndex":0,"jobIndex":0,"setIndex":0,"hairIndex":2,"eyeIndex":1,
  "eyeOffset":0,"mouthIndex":3,"mouthOffset":0,"skinColor":1,"hairColor":4,"sexType":0,
  "personalityType":1,"isWriteData":true,"result":{"funcResult":1,"lastStatus":0}}}"
```

### 4.2 StyleSelect

- **Path:** `POST /api/pollux/`
- **When:** the player unlocks a job style with a Happy Ticket.

**Request:** `open_style_index` (int): the style being opened, matching the save's `ticketUnlockedJobStyle` keys 1, 3 and 5. The older `jobIndex` and `styleIndex` keys are also accepted.

**Reply:** wrapper `JsonRadarResultStyleSelect`.

- `unlockTicketNum`: int, the Happy Tickets given (`presentTicketNum`) after the unlock.
- `isWriteData`: bool, `true`.
- `result`: the status object.

**Example:** `version:Ver_1_63_0,f:StyleSelect,pid:76561190000000001,open_style_index:1` → `"{"JsonRadarResultStyleSelect":{"unlockTicketNum":20,"isWriteData":true,"result":{"funcResult":1,"lastStatus":0}}}"`

### 4.3 ItemEquip

- **Path:** `POST /api/pollux/`
- **When:** the player leaves the equipment screen. This saves what is equipped and sells the items marked for sale.

**Request:**

| Key | Type | Meaning |
|---|---|---|
| `job_index`, `set_index`, `style_index` | int | Which profile |
| `h<s>`, `b<s>`, `r<s>`, `l<s>`, `a<s>` with `<s>` in 0, 1, 2, 100, 101, 102, 200, 201, 202 | int | The UniqueID in each slot (0 = empty). h = head, b = body, r = right hand, l = left hand, a = accessory. The suffix is style×100 + set. |
| `delete_item_num` | int | How many items are sold |
| `p0000` … `p<N-1>` | int | The UniqueIDs of the sold items |

**Reply:** wrapper `JsonRadarResultItemEquip`.

| Field | Type | Meaning |
|---|---|---|
| `jobIndex`, `setIndex`, `styleIndex` | int | Echoed when sent |
| `getHappyPointWithDelete` | object | Balances after the sale (below) |
| `isWriteData` | bool | `true` |
| `result` | object | Status object |

`getHappyPointWithDelete` holds:

- `HappyStar`, `HappyTicket`, `HappyCardTicket`, `HappyCardStarTicket`: int.
- `HappyCardJobTicket_W`, `HappyCardJobTicket_C`, `HappyCardJobTicket_M`: int, one per job.
- `BoostSpawnTicket`, `LoginBonusTicket`: int.
- `ItemSetID`: string, `ItemSet000` style.

**Example:**

```
version:Ver_1_63_0,f:ItemEquip,pid:76561190000000001,job_index:0,set_index:0,style_index:0,h0:4010001,h1:0,...,a202:0,delete_item_num:0
→ 200 "{"JsonRadarResultItemEquip":{"jobIndex":0,"setIndex":0,"styleIndex":0,"getHappyPointWithDelete":
  {"HappyStar":990099,"HappyTicket":20,"HappyCardTicket":0,"HappyCardStarTicket":1,"HappyCardJobTicket_W":1,
  "HappyCardJobTicket_C":1,"HappyCardJobTicket_M":1,"BoostSpawnTicket":0,"LoginBonusTicket":0,
  "ItemSetID":"ItemSet000"},"isWriteData":true,"result":{"funcResult":1,"lastStatus":0}}}"
```

### 4.4 ItemEnhance (item level-up)

- **Path:** `POST /api/pollux/`
- **When:** the player levels up an item with material items.

**Request:**

| Key | Type | Meaning |
|---|---|---|
| `base_item` | int | UniqueID of the item to level up |
| `material_0` … `material_5` | int | UniqueIDs of the materials (0 = empty slot) |
| `material_num` | int | How many material slots are used |
| `is_use_star` | 0 / 1 | Paid with stars |

**Reply:** wrapper **`RadarJsonResultItemEnhance`**. The server also sends a copy under `JsonRadarResultItemEnhance`, which the client does not read.

| Field | Type | Meaning |
|---|---|---|
| `result` | object | Status object |
| `enhanceResultItemSeed` | item seed | The item after levelling |
| `resultHappyPoint` | int | Stars left |
| `resultUseHappyTicket` | int | 0 |
| `successType` | int | 1 normal, 2 great, 3 super (the bonus roll) |
| `enhanceBaseItemSeed` | item seed | The item before |
| `enhanceMaterialItemSeed` | list of 6 item seeds | The materials used. Empty slots are empty-slot items. |
| `materialNum` | int | Materials used |
| `totalGetExp` | int | Experience gained |
| `limitBreakMatItemNum`, `limitBreakMatCount`, `limitBreakBuffMatItemNum`, `limitBreakCountByBuff` | int | Limit-break counts from the materials |
| `isUseStar` | 0 / 1 | Echo |
| `costHappyPoint` | int | Stars charged |
| `costHappyTicket` | int | 0 |

**Example (seeds shortened):**

```
version:Ver_1_63_0,f:ItemEnhance,pid:76561190000000001,base_item:4010001,is_use_star:0,material_0:1010002,
material_1:0,material_2:0,material_3:0,material_4:0,material_5:0,material_num:1
→ 200 "{"RadarJsonResultItemEnhance":{"result":{"funcResult":1,"lastStatus":0},
  "enhanceResultItemSeed":{"ID":"ITEM_WEPON_NON_0000","UniqueID":4010001,"Level":1,"EnhanceExperience":0.5,
  "EquipmentPart":0,"LimitBreakCount":0,"BuffSlot":0,"BaseRandomSeed":0,"EquipProfileIndex":-1,
  "First":false,"New":false},"resultHappyPoint":989447,"resultUseHappyTicket":0,"successType":1,
  "enhanceBaseItemSeed":{...},"enhanceMaterialItemSeed":[{...},{...},{...},{...},{...},{...}],
  "materialNum":1,"totalGetExp":100,"limitBreakMatItemNum":0,"limitBreakMatCount":0,
  "limitBreakBuffMatItemNum":0,"limitBreakCountByBuff":0,"isUseStar":0,"costHappyPoint":52,
  "costHappyTicket":0},"JsonRadarResultItemEnhance":{...same...}}"
```

### 4.5 ItemSynthesis (buff transfer and erase)

- **Path:** `POST /api/pollux/`
- **When:** the player moves buffs from a material item onto a base item, or erases buffs.

**Request:**

| Key | Type | Meaning |
|---|---|---|
| `base_item_unique_id` | int | The item that gets the buffs |
| `material_item_unique_id` | int | The item that gives them (it is used up) |
| `selectedBuff_0` … `selectedBuff_3` | string | The buff picked for each slot of the base, or `(null)` |
| `delete_buff_target_unique_id` | int | The item to erase buffs from (0 = none) |
| `delete_buff_0` … `delete_buff_3` | string | The buffs to erase |
| `is_use_star` | 0 / 1 | Paid with stars |

**Reply:** wrapper **`RadarJsonResultItemSynthesis`**, plus an unread copy under `JsonRadarResultItemSynthesis`.

| Field | Type | Meaning |
|---|---|---|
| `result` | object | Status object |
| `synthResultBaseItemSeed` | item seed | The base after the transfer |
| `synthResultMaterialItemSeed` | item seed | The material (now used up) |
| `deleteBuffResultTargetItemSeed` | item seed | The erase target after the erase, or an empty-slot item |
| `resultHappyPoint` | int | Stars left |
| `resultUseHappyTicket` | int | 0 |
| `deleteBuffs` | list of strings | The buff ids erased |
| `isUseStar` | 0 / 1 | Echo |
| `costHappyPoint` | int | Stars charged |
| `costHappyTicket` | int | 0 |

**Example (seeds shortened):**

```
version:Ver_1_63_0,f:ItemSynthesis,pid:76561190000000001,base_item_unique_id:4010001,
material_item_unique_id:1010003,delete_buff_target_unique_id:0,selectedBuff_0:(null),selectedBuff_1:(null),
selectedBuff_2:(null),selectedBuff_3:(null),is_use_star:0
→ 200 "{"RadarJsonResultItemSynthesis":{"result":{"funcResult":1,"lastStatus":0},
  "synthResultBaseItemSeed":{...},"synthResultMaterialItemSeed":{...},"deleteBuffResultTargetItemSeed":{...},
  "resultHappyPoint":989047,"resultUseHappyTicket":0,"deleteBuffs":[],"isUseStar":0,"costHappyPoint":400,
  "costHappyTicket":0},"JsonRadarResultItemSynthesis":{...same...}}"
```

---

## 5. Spinner (Happy Spinner, Happy Cards, Limited Edition packs)

- **Path:** `POST /api/pollux/`
- **When:** the Spinner and Happy Card screens. The game also calls it on every tab switch to sync the screen.

**Request:**

| Key | Type | Meaning |
|---|---|---|
| `kind` | int | 0 = Happy Spinner wheel, 1 = normal Happy Card, 2 = Limited Edition (series) pack. Default 1. |
| `costtype` | int | 1 = Happy Stars (wheel), 2 = Happy Tickets (or a tab sync), 3 = Happy Card ticket. Default 2. |
| `jobtype` | int | The job ticket used for a Happy Card: 0 warrior, 1 cleric, 2 mage. -1 = none. |
| `bet00` … `bet05` | int | Wheel: the category of each chip placed (0-4; -1 or absent = no chip). Card: the pack category copied into all six (0 weapon, 1 shield, 2 helmet, 3 armor, 4 accessory). All 0 on a tab sync. |
| `category`, or a tab field such as `tab`, `tabIndex`, `tabCategory` | int | Optional. The tab shown; it marks the request as a tab sync. |

The server reads the request this way:

- **Tab sync:** all bets are 0 and there is a tab field, or all bets are 0 on a costtype that is not a card. Nothing is spent and `itemSeed` is `[]`.
- **Card draw:** costtype 3, or kind 2 with costtype 2. The game has already spent the pass, ticket or star ticket, and the reply gives 3 items (2 normal, 1 rare).
- **Wheel spin:** kind 0, costtype 1 and at least one chip placed.

**Reply:** wrapper `JsonRadarResultSpinner`. Every case has the same fields:

| Field | Type | Meaning |
|---|---|---|
| `category` | int | Card or sync: the category shown. Wheel: where the wheel stopped (0-4 = a category, 5 random, 6 lucky, 7 blank). |
| `date` | int | `YYYYMMDD`. For a kind-2 pack, the pack's series date. |
| `happyPoint` | int | The Happy Time meter (0-24). Wheel: 0. |
| `happyStarNum` | int | Stars after the spin |
| `happyTicketNum` | int | 0 |
| `happyTicketUseNum` | int | Tickets spent on this spin |
| `happyCardTicketNum` | int | Always 2. Its meaning is not known yet. |
| `happyCardStarTicketNum` | int | Happy Card star tickets (at least 1) |
| `jobTypeTicketNum` | int[3] | Job tickets after the draw `[W,C,M]` |
| `itemSeed` | list of item seeds | Items won |
| `playCount` | int | The player's spin counter |
| `kind`, `costtype`, `jobtype` | int | Echo (the wheel always answers `costtype` 1) |
| `starfrag` | int | Star fragments used |
| `bet00` … `bet05` | int | Bets as the server applied them (wheel: echoed, -1 when absent) |
| `isWriteData` | bool | `true` |
| `result` | object | Status object |

**Example (Happy Card draw):**

```
version:Ver_1_63_0,f:Spinner,pid:76561190000000001,kind:1,costtype:3,jobtype:0,bet00:0,bet01:0,bet02:0,bet03:0,bet04:0,bet05:0
→ 200 "{"JsonRadarResultSpinner":{"category":0,"date":20261120,"happyPoint":2,"happyStarNum":990099,
  "happyTicketNum":0,"happyTicketUseNum":0,"happyCardTicketNum":2,"happyCardStarTicketNum":1,
  "jobTypeTicketNum":[0,1,1],"itemSeed":[{"ID":"ITEM_WEPON_0570","UniqueID":100000000,"Level":1,
  "EnhanceExperience":0.0,"EquipmentPart":0,"LimitBreakCount":0,"BuffSlot":["Buff_BlowAttackLvl_01","","",""],
  "BaseRandomSeed":0,"EquipProfileIndex":-1,"First":false,"New":true},{...ITEM_WEPON_0380...},
  {...ITEM_WEPON_0290...}],"playCount":43,"kind":1,"costtype":3,"jobtype":0,"starfrag":0,
  "bet00":0,"bet01":0,"bet02":0,"bet03":0,"bet04":0,"bet05":0,"isWriteData":true,
  "result":{"funcResult":1,"lastStatus":0}}}"
```

**Example (wheel with chips on weapon and armor; it stopped on blank):**

```
version:Ver_1_63_0,f:Spinner,pid:76561190000000001,kind:0,costtype:1,jobtype:-1,bet00:0,bet01:2,bet02:-1,bet03:-1,bet04:-1,bet05:-1
→ 200 "{"JsonRadarResultSpinner":{"category":7,"date":20261120,"happyPoint":0,"happyStarNum":989499,
  "happyTicketNum":0,"happyTicketUseNum":0,"happyCardTicketNum":2,"happyCardStarTicketNum":1,
  "jobTypeTicketNum":[0,1,1],"itemSeed":[],"playCount":44,"kind":0,"costtype":1,"jobtype":-1,"starfrag":0,
  "isWriteData":true,"result":{"funcResult":1,"lastStatus":0},"bet00":0,"bet01":2,"bet02":-1,"bet03":-1,
  "bet04":-1,"bet05":-1}}"
```

---

## 6. Purchase calls (Happy Ticket shop)

These go to the **purchase server**, not to `/api/pollux/`:

- **Path:** `POST /api/<Function>`, with no `f`.
- **Body:** plain JSON. The ids are bare JSON numbers.
- **Headers:** the same as the Pollux calls.
- **Reply:** quoted JSON (1.4) under a `RadarJsonResult*` wrapper. `result` is the **string** `"OK"`, or `"Failure"`.

A failure carries `{"errorcode":"<n>","errordesc":"<text>"}`:

- InitTxn reads it under `error`.
- FinalizeTxn reads it under `response`.
- The server sends both.

For FinalizeTxn, `errorcode` `"10"` is not treated as an error.

The six packs belong to the client: its game data (`ticketPanelDetails_`) defines them, and the server only lists their price and order.

| Panel | AssetID | Icon | Tickets |
|---|---|---|---|
| Panel_00 | 101004 | 1 | 16 |
| Panel_01 | 101002 | 3 | 40 |
| Panel_02 | 101005 | 4 | 80 |
| Panel_03 | 101006 | 6 | 160 |
| Panel_04 | 101008 | 7 | 240 |
| Panel_05 | 101009 | 8 | 320 |

### 6.1 HappyTicketAsset

- **Path:** `POST /api/HappyTicketAsset`
- **When:** the shop dialog opens.

**Request:** `{"steamid":<number>,"appid":246280}`.

**Reply:** wrapper `RadarJsonResultHappyTicketAsset`: `{"result":"OK","response":{"assets":[...]}}`. Each asset has:

| Field | Type | Meaning |
|---|---|---|
| `panelKey` | string | `Panel_00` … `Panel_05` |
| `assetId` | int | Must match the client's AssetID. If an asset is missing, the dialog closes with message `$TXCDI00039`. |
| `iconId` | int | Icon |
| `logical_no` | int | Order |
| `discount_no` | int | 0 |
| `cost` | float | The price shown as ` $%3.2f` |

**Example:**

```
POST /api/HappyTicketAsset
{"steamid":76561190000000001,"appid":246280}
→ 200 "{"RadarJsonResultHappyTicketAsset":{"result":"OK","response":{"assets":[
  {"panelKey":"Panel_00","assetId":101004,"iconId":1,"logical_no":0,"discount_no":0,"cost":0.0},
  {"panelKey":"Panel_01","assetId":101002,"iconId":3,"logical_no":1,"discount_no":0,"cost":0.0},
  ... Panel_02..Panel_05 ...]}}}"
```

### 6.2 HappyTicketSum

- **Path:** `POST /api/HappyTicketSum`
- **When:** once after TitleLogin, after the asset list, and after every FinalizeTxn.

**Request:** `{"steamid":<number>,"appid":246280}`

**Reply:** wrapper **`RadarJsonResultBoughtTicketNum`** (not `...HappyTicketSum`): `{"result":"OK","response":{"happyticket":<int>}}`.

- `happyticket` is the number of tickets **bought on top of** the save's count.
- The game shows `presentTicketNum + happyticket − useTicketNum`, capped at 999.
- So if purchases are written into the save, this field must count only the tickets the game has not loaded yet. Otherwise they show twice.

**Example:** after one 16-ticket purchase:

```
POST /api/HappyTicketSum
{"steamid":76561190000000001,"appid":246280}
→ 200 "{"RadarJsonResultBoughtTicketNum":{"result":"OK","response":{"happyticket":16}}}"
```

The original live purchase server answered the same shape with `"happyticket":999`.

### 6.3 InitTxn

- **Path:** `POST /api/InitTxn`
- **When:** the player picks a pack.

**Request:** `{"steamid":<number>,"appid":246280,"language":"EN","assetid":<AssetID>}`

**Reply:** wrapper `RadarJsonResultInitTxn`.

- **OK:** `{"result":"OK","response":{"orderid":<int>}}`.
  - The order id must be new for every order and **at most 2147483647**: the client stores it in 32 bits and clamps larger values.
  - Each order id is approved once.
- **Failure:** `{"result":"Failure","error":{"errorcode":"<n>","errordesc":"<text>"}}`. The game then shows its generic "purchase could not be completed" message.

**Example:**

```
POST /api/InitTxn
{"steamid":76561190000000001,"appid":246280,"language":"EN","assetid":101004}
→ 200 "{"RadarJsonResultInitTxn":{"result":"OK","response":{"orderid":1}}}"
(unknown pack) → 200 "{"RadarJsonResultInitTxn":{"result":"Failure","response":{"errorcode":"2","errordesc":"unknown pack"},
                 "error":{"errorcode":"2","errordesc":"unknown pack"}}}"
```

### 6.4 FinalizeTxn

- **Path:** `POST /api/FinalizeTxn`
- **When:** after the player approves the order.

**Request:** `{"steamid":<number>,"appid":246280,"orderid":<int>,"authorized":1}`. `authorized` is 1 when approved.

**Reply:** wrapper `RadarJsonResultFinalizeTxn`.

- **OK:** `{"result":"OK"}`, and the pack's tickets are credited once per order.
- **Failure:** `{"result":"Failure","response":{"errorcode":"<n>","errordesc":"<text>"}}`.

**Example:**

```
POST /api/FinalizeTxn
{"steamid":76561190000000001,"appid":246280,"orderid":1,"authorized":1}
→ 200 "{"RadarJsonResultFinalizeTxn":{"result":"OK"}}"
(unknown order) → 200 "{"RadarJsonResultFinalizeTxn":{"result":"Failure","response":{"errorcode":"4","errordesc":"unknown order"},
                  "error":{"errorcode":"4","errordesc":"unknown order"}}}"
```

**Revival failure codes:** 2 unknown pack, 3 daily limit reached, 4 unknown order, 5 not authorized.

---

## 7. Match calls

### 7.1 RecordMatching

- **Path:** `POST /api/pollux/`
- **When:** around matchmaking, to load or add to the player's host and connection record.

**Request:** Pollux classic.

| Key | Type | Meaning |
|---|---|---|
| `is_load_only` | 0 / 1 | 1 = only read the counts |
| `add_host_count` | int | Matches hosted to add |
| `add_host_error_count` | int | Host errors to add |
| `add_lagged_count` | int | Lagged matches to add |
| `reset_version` | int | Counter reset version |

**Reply:** wrapper **`RadarJsonResultRecordMatching`**.

The client reads only the `result*` keys:

| Field | Type | Meaning |
|---|---|---|
| `result` | object | Status object |
| `resultHostCount` | int | Total matches hosted |
| `resultHostErrorCount` | int | Total host errors |
| `resultLaggedCount` | int | Total lagged matches |
| `resultGameCount` | int | Games counted (0) |

The server also sends un-prefixed copies (`isLoadOnly`, `hostCount`, `hostErrorCount`, `laggedCount`, `resetVersion`). They come from a sample inside the client and are not read. The reply also carries host-penalty fields, listed under Excluded.

**Example (penalty fields left out):**

```
version:Ver_1_63_0,f:RecordMatching,pid:76561190000000001,is_load_only:1,add_host_count:0,add_host_error_count:0,add_lagged_count:0,reset_version:0
→ 200 "{"RadarJsonResultRecordMatching":{"result":{"funcResult":1,"lastStatus":0},"resultHostErrorCount":0,
  "resultHostCount":0,"resultLaggedCount":0,"resultGameCount":0,"isLoadOnly":1,"hostCount":0,
  "hostErrorCount":0,"laggedCount":0,"resetVersion":0, ...}}"
```

### 7.2 MapVote (launcher DLL, Quick Match lobby)

- **Path:** `POST /api/pollux/`
- **When:** the revival launcher DLL sends this, not the game. It runs about every 2 s while a Quick Match lobby is on screen, so every player sees the same three maps and the same winner.

**Request:** JSON.

| Key | Type | Meaning |
|---|---|---|
| `f` | `MapVote` | |
| `pid` | string | Steam id |
| `lobby` | string | The Steam lobby id |
| `pool` | hex string | Bit mask of the stage kinds 0-31 this game data can pick |
| `round` | int | The round this vote is for (0 = none yet) |
| `vote` | int | The row voted for: 0-2, 3 = "none of the above" (v2), -1 = none |
| `rotate` | 0 / 1 | Asks for three other maps (v1) |
| `v` | 1 / 2 | Protocol version. 2 = timed vote. |
| `start` | 0 / 1 | v2, host only: the lobby is ready (match found) and the timed round opens |
| `done` | int | Host only: the round its last match played |
| `from` | string | Optional: the lobby a lone host just left |

**Reply:** plain JSON, with no quotes and no wrapper.

```
{"status":"ok","round":r,"kinds":[a,b,c],"votes":[x,y,z],"agree":n,"voters":m,"winner":kind,"mine":row,
 "phase":p,"endsIn10":t,"nota":k,"veto":0|1,"final":kind|-1}
```

| Field | Type | Meaning |
|---|---|---|
| `kinds` | int[3] | The three stage kinds shown (-1 = no map) |
| `votes` | int[3] | Votes per row |
| `agree` | int | Players asking to rotate |
| `voters` | int | Players heard from in the last 10 s |
| `winner` | int | The leading stage kind. Ties are settled by a fixed per-round order. |
| `mine` | int | This player's vote this round, or -1 |
| `phase` | int | 0 open, 1 timed, 2 final |
| `endsIn10` | int | Tenths of a second left in a timed round |
| `nota` | int | "None of the above" votes |
| `veto` | 0 / 1 | The one re-draw was used |
| `final` | int | The winner once `phase` is 2, else -1 |

Errors are plain JSON `{"status":"error","error":"..."}`:

- 400 when `pid` or `lobby` is not a Steam id, or when `pool` is not hex.
- 500 for a storage problem.
- 503 for too many lobbies.

**Example:**

```
{"f":"MapVote","pid":"76561190000000001","lobby":"109775240000000001","pool":"ffff","round":0,"vote":-1,"rotate":0}
→ 200 {"status":"ok","round":1,"kinds":[3,0,2],"votes":[0,0,0],"agree":0,"voters":1,"winner":0,"mine":-1,
       "phase":0,"endsIn10":0,"nota":0,"veto":0,"final":-1}
```

### 7.3 LoadingGameStart / LoadingGameEnd

- **Path:** `POST /api/pollux/`
- **When:** at the start and end of the match load screen.

**Request:** `version:Ver_1_63_0,f:LoadingGameStart,pid:<steam id>` (or `f:LoadingGameEnd`).

**Reply:** wrapper `JsonRadarResultLoadingGameStart` or `JsonRadarResultLoadingGameEnd`, with `{"result":"OK"}`. `result` is the **string** "OK", not the status object. The client only checks for success.

**Example:** `→ 200 "{"JsonRadarResultLoadingGameStart":{"result":"OK"}}"` and `→ 200 "{"JsonRadarResultLoadingGameEnd":{"result":"OK"}}"`

### 7.4 GameResult

- **Path:** `POST /api/pollux/`
- **When:** after every match, including tutorial, story and skirmish.

**Request:** Pollux classic with numbered `pNNN` keys. The client sends many keys; the table lists those whose meaning is known. Unknown keys are sent too, and the server ignores them.

| Key | Type | Meaning |
|---|---|---|
| `p001` | int | Mode: 3 = skirmish (Wars, offline), 4 = Quick Match. This picks the battle-record column. |
| `p007` | 0 / 1 | 1 = win |
| `p010` | 0 / 1 | Ended on time |
| `p013`, `p014` | int | Your team's league and the opposing team's league |
| `p017` | string | Stage or campaign name: `cam_TUTORIAL_01`, `cam_STORY_01`…`06`, `cam_WARS_*`. Empty online. |
| `p018` | string | Mission or rule name, e.g. `mission00` |
| `p019` | int | Difficulty |
| `p101` | int | Play time in seconds |
| `p102`, `p103` | int | Total and longest life |
| `p115` + `00`…`05` | int | Kills by category (6 entries) |
| `p118` + `00`…`05` | int | Deaths by category (6 entries) |
| `p116`, `p119`, `p120`, `p121`, `p117`, `p129`…`p132`, `p134`, `p142`, `p145`…`p148` + `00`…`05` | int | More 6-wide category tallies. `p129` = time alive per job. |
| `p138` | int | Medal or placement tier |
| `p144` + `00`…`08` + `k`/`s`/`t` | int | A 3×3 grid of score legs: cell = class×3 + set. `k` = killing, `s` = support, `t` = tactics. |
| `p002`…`p029`, `p104`…`p114`, `p122`…`p128`, `p133`, `p135`…`p137`, `p139`…`p141`, `p143` | int / string | Sent. Meaning unknown, and the server does not use them. |

The match score is the sum of `k` and `s` over the `p144` grid.

**Reply:** wrapper `JsonRadarResultGameResult`, **flat**. `result` and 29 more keys sit directly under the wrapper, with no `response` sub-object.

| Field | Type | Meaning |
|---|---|---|
| `result` | object | `{"funcResult":1,"lastStatus":0}` |
| `isUnlockedJobStyleByTicket` | bool | `true` |
| `rewardItemError` | int | 0 |
| `cooperativeComplete` | bool | Co-op goal met |
| `cooperativeWinCount` | int | Co-op wins |
| `cooperativeScoreBonusRank`, `cooperativeScoreBonus`, `cooperativeStrongBonus`, `cooperativeDefaultBonus` | int | Co-op bonuses |
| `cooperativeRewardItem` | list of item seeds | Co-op rewards |
| `missionRewardHappyStar` | int | Stars from a first clear |
| `missionRewardItemSeed` | list of item seeds | Items from a first clear |
| `missionIndex` | int | Offline: the mission played. The client checks this against its own value. Online: -1. |
| `campaignIndex` | int | Offline: the campaign played (tutorial 1, story 14-19, skirmish by stage). Online: -1. |
| `rewardHappyStar` | int | Total stars gained |
| `rewardItem` | list of item seeds | Items dropped |
| `friendBonusScoreRate`, `friendBonusStarRate` | **float** | Friend bonus rates. `1.0` = none. Must be floats. |
| `friendNum` | int | Friends in the match |
| `evaluationValue` | int list | Evaluation values. The server sends 20, starting with score, killing, support, tactics, kills, deaths, win and placement. The client accepts any length; the meaning of each slot is not known yet. |
| `reachMaxLevelCount` | int | 0 |
| `oneGameScoreMax` | int | This match's score |
| `totalHppyStarNum` | int | Stars after the match (spelled this way) |
| `totalHappyTicketNum`, `totalHappyTicketUseNum`, `totalHappyCardTicketNum` | int | Totals (1.8) |
| `totalJobTypeTicketNum` | int[3] | Job tickets |
| `baseHistory` | object | Before the match: `MedalRank` int, `KillingScore` / `SupportScore` / `TacticsScore` int[3][3], `LeaguePoint` int, `RankLeague` int, `HighRankLeague` bool, `AchievedQuest` bool[90] |
| `resultHistory` | object | The same shape, after the match |
| `itemGrowthInfo` | object | `{}` |

**Nesting rules:**

- Keep everything flat under the wrapper.
- When `missionIndex` and `campaignIndex` do not match what the client played offline, or a first clear sends `missionRewardItemSeed` as `[]` where items are due, the game shows "network error (124)".
- Happy Cards appear only as `totalHappyCardTicketNum`. GameResult has no card list.

**Example (Quick Match win):**

```
version:Ver_1_63_0,f:GameResult,pid:76561190000000001,p001:4,p007:1,p010:0,p013:1,p014:1,p017:cam_WARS_01,
p018:mission00,p019:0,p101:600,p102:600,p103:300,p138:2,p139:0,p11500:1,...,p11505:1,p11800:0,...,
p12900:100,...,p14400k:120,p14400s:40,p14400t:30,p14401k:0,...,p14408t:0
→ 200 "{"JsonRadarResultGameResult":{"result":{"funcResult":1,"lastStatus":0},"isUnlockedJobStyleByTicket":true,
  "rewardItemError":0,"cooperativeComplete":false,"cooperativeWinCount":0,"cooperativeScoreBonusRank":0,
  "cooperativeScoreBonus":0,"cooperativeStrongBonus":0,"cooperativeDefaultBonus":0,"cooperativeRewardItem":[],
  "missionRewardHappyStar":0,"missionRewardItemSeed":[],"missionIndex":-1,"campaignIndex":-1,
  "rewardHappyStar":160,"rewardItem":[],"friendBonusScoreRate":1.0,"friendBonusStarRate":1.0,"friendNum":0,
  "evaluationValue":[160,120,40,30,6,0,1,2,0,0,0,0,0,0,0,0,0,0,0,0],"reachMaxLevelCount":0,
  "oneGameScoreMax":160,"totalHppyStarNum":989207,"totalHappyTicketNum":20,"totalHappyTicketUseNum":30,
  "totalHappyCardTicketNum":0,"totalJobTypeTicketNum":[0,1,1],
  "baseHistory":{"MedalRank":1,"KillingScore":[[0,0,0],[0,0,0],[0,0,0]],"SupportScore":[[0,0,0],[0,0,0],[0,0,0]],
   "TacticsScore":[[0,0,0],[0,0,0],[0,0,0]],"LeaguePoint":0,"RankLeague":1,"HighRankLeague":false,
   "AchievedQuest":[false,...90 entries...]},
  "resultHistory":{"MedalRank":1,"KillingScore":[[120,0,0],[0,0,0],[0,0,0]],"SupportScore":[[40,0,0],[0,0,0],[0,0,0]],
   "TacticsScore":[[30,0,0],[0,0,0],[0,0,0]],"LeaguePoint":0,"RankLeague":1,"HighRankLeague":false,
   "AchievedQuest":[false,...]},"itemGrowthInfo":{}}}"
```

### 7.5 Mission

- **Path:** `POST /api/pollux/`
- **When:** the mission (quest) screen claims or syncs a mission.

**Request:**
- `mission_index` (int): the mission.
- `history` (digit string): sent but not used.

**Reply:** wrapper `JsonRadarResultMission`.

| Field | Type | Meaning |
|---|---|---|
| `result` | object | Status object |
| `missionIndex` | int | Echo |
| `isAchievedMission` | bool | The mission is done |
| `isWriteData` | bool | `true` |
| `completedCampaignMission`, `achieveMissionFlag`, `historyMissionFlag` | string | One `'0'` or `'1'` per mission (420 characters) |
| `totalHappyStarNum` … `totalLoginBonusTicketNum` | int / int[3] | Totals (1.8, all eight) |
| `rewardItemSeed` | list of item seeds | Reward items. Given on the first claim only. |
| `missionData` | list of 512 objects | Each `{"index":<int or -1>,"isActive":bool,"isComplete":bool}` |
| `missionKey` | string | The mission's key, e.g. `mission_000` |

The rewards come from the mission's reward set (stars, Happy Tickets, Happy Card tickets, star tickets, boost and job tickets), and the totals show them.

**Example (shortened):**

```
version:Ver_1_63_0,f:Mission,pid:76561190000000001,mission_index:0,history:0
→ 200 "{"JsonRadarResultMission":{"result":{"funcResult":1,"lastStatus":0},"missionIndex":0,
  "isAchievedMission":false,"isWriteData":true,"completedCampaignMission":"0000...(420)",
  "achieveMissionFlag":"0000...(420)","historyMissionFlag":"0000...(420)","totalHappyStarNum":990099,
  "totalHappyTicketNum":20,"totalHappyTicketUseNum":30,"totalHappyCardTicketNum":0,
  "totalHappyCardStarTicketNum":1,"totalJobTypeTicketNum":[1,1,1],"totalBoostSpawnTicketNum":0,
  "totalLoginBonusTicketNum":0,"rewardItemSeed":[],"missionData":[{"index":-1,"isActive":false,
  "isComplete":false}, ...512 entries...],"missionKey":"mission_000"}}"
```

### 7.6 UploadTelemetry

- **Path:** `POST /api/pollux/`
- **When:** at any time; fire-and-forget.

**Request:** `version:...,f:UploadTelemetry,pid:<steam id>` plus telemetry fields. The server stores none of them.

**Reply:** wrapper `JsonRadarResultUploadTelemetry`, with `{"result":{"funcResult":1,"lastStatus":0}}`. The 1.63 client does not have this wrapper name, so only HTTP 200 matters.

**Example:** `→ 200 "{"JsonRadarResultUploadTelemetry":{"result":{"funcResult":1,"lastStatus":0}}}"`

---

## 8. Not yet known

- Which TitleLogin fields the 1.63 client reads.
- The meaning of each `evaluationValue` slot. The server's layout is its own.
- Whether `missionRewardItemSeed` and `cooperativeRewardItem` are item objects or plain numbers to the client. The examples here send objects.
- The meaning of many GameResult `pNNN` request keys (listed as unknown above).
- Spinner: the meaning of the fixed `happyCardTicketNum` 2. The reply for Limited Edition (kind 2) packs has not been tried yet.

Written by Serenity, Game Preservation HQ.
