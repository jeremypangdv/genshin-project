# Freminet 語音聊天機器人

目標：用 Freminet（菲米尼）的中文語音訓練一個 GPT-SoVITS 語音模型，之後再接上 LLM，做一個可以和角色對話、並用他的聲音回覆的聊天程式。

## 目前進度

- [x] 下載 Freminet 中文語音資料
- [x] 整理成 GPT-SoVITS 訓練格式（`freminet.list`）
- [x] 訓練語音模型（v2ProPlus，本地，2026-10-05，見[訓練結果](#訓練結果)）
- [ ] 挑選參考音頻（已按情緒選好 37 段候選，目前每種情緒都用第一段，還要試聽確定）
- [ ] 確定用哪個輪數
  - [x] GPT：用第 10 輪（第 15 輪聊天時常吞字，2026-10-05 換掉）
  - [ ] SoVITS：目前用第 8 輪，還沒和第 4 輪比較（`python scripts/tts.py` 裏 `/sovits e4`）
- [x] 寫角色資料：`characters/freminet.md`（bilibili wiki + 353 句官方語音整理：身世、個性、喜好、佩伊、對其他角色的看法、情緒指引）
  - [x] 2026-10-07 改成像朋友聊天：開頭加「怎樣聊天」的原則（先回應對方、自己的事偶爾才提），台詞範例減到 4 句，加日常聊天範例和「平時的生活」清單。之前他會照背台詞
- [x] 聊天 App（**可以用了**，雙擊 `Freminet Chat.exe`，見[聊天 App](#聊天-app)）
  - 2026-10-08：做成 exe，用自己的視窗打開（860×860 正方形，像電腦版聊天軟件），不開瀏覽器；拿掉 `start_chat.bat`
  - 2026-10-08：背景可以一次上傳多張、可以刪除；上傳只收 JPG / PNG，至少 860×860
  - 2026-10-08：小菲米尼跟着滑鼠，指着按鈕 / 輸入欄時換圖（輸入欄時移到右上角，不擋字）；語音訊息可以下載
  - 2026-10-08：自己畫的鼠標（SVG，冰藍 / 金色 / 深藍，一般、可以點、打字三種）
  - 2026-10-09：名稱從 Teyvat Chat 改成 Genshin Chat，視窗圖示用菲米尼頭像；清空聊天記錄重新開始
  - 類似 WhatsApp，菲米尼用語音訊息回覆，播放時顯示字幕，頭像用他的照片
  - 他會自己選情緒（9 種），用對應的參考音頻念
  - 聊天記錄會保存；吞字會自動重念
  - 2026-10-08：聊天畫面鋪滿整個視窗，不顯示好友列表；聊天背景可以在設定裏切換、下載、上傳（圖放在 `freminet profile/Background/`）；右上角可以隱藏聊天記錄，只看背景圖；菲米尼會像地鼠一樣從輸入欄後面探頭，點他會飄出愛心
  - 用這部電腦的 `qwen3:8b`（`active` 是 `ollama_8b`），之前是 `qwen3:4b-instruct`
  - 2026-10-10：清空聊天記錄會連語音檔一起刪；語音只留最近 50 則，更早的只剩文字，不會越積越大
- [x] ~~在另一部電腦跑 `qwen3:14b`~~：2026-10-10 決定不用了，就用這部的 `qwen3:8b`（`ollama_8b`）。`server/` 的 notebook 和 `server` 設定先留着
  - [x] 寫好 `server/install_server.ipynb` 和 `server/start_server.ipynb`（2026-10-07 從 bat 檔改成 notebook）
  - [x] 這部電腦裝好 Tailscale（2026-10-07，這部的 IP 是 `100.90.10.112`）
  - [x] 那部電腦裝好 Tailscale（同一個帳號，IP 是 `100.107.228.94`），已填進 `config/llm.json` 的 `server`
- [x] 決定用本地模型還是 API（2026-10-10：用本地 `qwen3:8b`）：比較簡報 https://claude.ai/artifact/C4JQrqPKo8T9QSAaTbEwWc （8b / 14b / DeepSeek / Qwen / GPT Luna 的價格和好壞，2026-10-07）
- [x] 給別的電腦用的準備（2026-10-07）
  - GPT-SoVITS 的路徑寫在 `config/tts.json`
  - `active` 是 `server` 時，`Freminet Chat.exe` 不會開本地 Ollama，那部電腦不用裝
  - 沒有 NVIDIA 顯卡就自動改用 CPU（能用但每句要 30 秒以上）
- [x] 打包給朋友（2026-10-09）：先 `build_exe.bat`，再 `python scripts/make_bundle.py`，做出 `dist/Freminet Chat/`（約 21.5GB），朋友雙擊 exe 就能用，不用裝任何東西
  - 裏面有 GPT-SoVITS（拿掉訓練用的東西，它的 Python 也用來跑聊天程式）、Ollama + `qwen3:8b`（用 11435 埠，不和朋友自己的 Ollama 撞）
  - 不包括這部電腦的聊天記錄；最好有 NVIDIA 顯卡
  - 2026-10-09 測試過：打包版能開、語音和回覆正常。給朋友時把 `dist/Freminet Chat/` 整個資料夾給他們
  - 2026-10-10：關掉聊天視窗會一起關掉自帶的 Ollama（不然模型一直佔着顯卡），測試過約 2 分鐘後全部關掉
  - 壓縮前先刪掉自己測試留下的 `app.log` 和 `tts_output/` 裏的 wav；`chats/` 要是空的
- [x] 長期記憶：舊對話整理成摘要（見[聊天 App](#聊天-app)）
  - 2026-10-10：記憶分成「對方的資料」（名字、寵物、生日…只加不刪）和話題摘要；用模擬長聊天測過，說過的事大多記得
  - 2026-10-10：不記得的事老實說忘了、請對方再說，不亂猜；但 8b 說「忘了」時句型常常一樣，試過改不了，先保持
- [x] 2026-10-10 改成剛認識：對方不是旅行者，菲米尼不認識你，從拘謹慢慢變熟（`characters/freminet.md` 的「和對方的關係」）

## 資料

來源：[simon3000/genshin-voice](https://huggingface.co/datasets/simon3000/genshin-voice) 的 `speaker-archives/Chinese/11-500/Freminet.zip`。整個 dataset 約 360GB，這個 zip 只有 175MB。

資料位置：`freminet_chinese/`（不放進 git，見 `.gitignore`）

| 內容 | 數量 |
|---|---|
| 全部 `.wav`（48kHz） | 411 段，約 46.5 分鐘 |
| 訓練用（`freminet.list`） | 353 段，約 45 分鐘 |
| 不放進訓練：沒有文本的戰鬥聲音 | 52 段（檔案保留，不刪除） |
| 不放進訓練：文本含 `{NICKNAME}` | 6 段（文本和音頻對不上） |

- `metadata.csv`：所有音頻的檔名、文本、時長
- `freminet.list`：GPT-SoVITS 訓練列表，格式 `音頻路徑|Freminet|zh|文本`
- 重新生成列表：`python scripts/make_sovits_list.py`

## 電腦配置

聊天電腦（跑 GPT-SoVITS 和聊天介面）：

- 顯卡：RTX 3060 Laptop，**6GB 顯存**
- 記憶體：16GB
- GPT-SoVITS：`D:\characters\GPT-SoVITS-Rin\GPT-SoVITS-v2pro-20250604`（2025-06 整合包，v2Pro / v2ProPlus / v4 底模都已齊全，不用下載）。路徑寫在 `config/tts.json`，別的電腦要改成自己的路徑（用 `/` 分隔）

LLM 伺服器（只跑 Ollama，見 [LLM 伺服器](#llm-伺服器)）：

- Ryzen 7 260、RTX 5060 Laptop 115W，**8GB 顯存**、16GB 記憶體、1TB SSD

## 語音模型訓練方案

### 決定

- **版本：v2ProPlus**。官方說效果超過 v4，生成速度快，6GB 顯存跑得動。
- **在本地電腦訓練**，不用 Colab / Kaggle。
- 只有以下情況才改：
  - 爆顯存 → 先把 batch size 調成 1，還是不行改用 v2Pro
  - 之後想試 v4 → 用 Kaggle 訓練來比較（Kaggle 比 Colab 穩定）

### 訓練前準備

1. 筆電接上電源，電源模式設成「最佳效能」
2. 關掉佔用顯卡的程式（遊戲、Discord、瀏覽器硬件加速等）
3. 執行 `go-webui.bat`

### 步驟

1. **選版本**：WebUI 最上方選 `v2ProPlus`
2. **1A 資料格式化**
   - 實驗名稱：`Freminet`
   - 文本標註文件：`E:\genshin-project\freminet_chinese\freminet.list`
   - 訓練集音頻文件目錄：**留空**（列表裏已經是完整路徑）
   - 按「一鍵三連」
3. **1B 訓練 SoVITS**（先訓練這個）

   | 參數 | 值 |
   |---|---|
   | batch size | 2（順利可試 3–4） |
   | epochs | 8 |
   | 保存頻率 | 每 4 輪 |
   | 半精度 | 開啟 |

4. **1B 訓練 GPT**

   | 參數 | 值 |
   |---|---|
   | batch size | 2（順利可試 3–4） |
   | epochs | 10–15（不要太多，會過擬合） |
   | 保存頻率 | 每 5 輪 |
   | DPO | 關閉（6GB 不夠） |

5. **1C 推理測試**
   - 參考音頻：挑一段 3–10 秒、語氣平穩、沒有喘氣或叫聲的原聲，文本從 `metadata.csv` 查
   - 試不同輪數保存下來的模型組合，挑效果最好的

6. **匯出模型**：把選好的模型複製到 `Models/Freminet/`（不放進 git，見 `.gitignore`）
   - SoVITS：GPT-SoVITS 目錄下 `SoVITS_weights_v2ProPlus/Freminet_e*_s*.pth`
   - GPT：GPT-SoVITS 目錄下 `GPT_weights_v2ProPlus/Freminet-e*.ckpt`
   - 參考音頻按情緒放在 `refs/<情緒>/`（calm、happy、gentle、sad、shy、surprised、serious、angry、urgent），每種情緒的音頻和文本寫在 `model.json`，列表第一個是預設

**也可以不用 WebUI**：`train_freminet.ipynb` 用同樣的參數執行 1A、1B 和匯出，可以直接全部執行（用最後一輪的模型，每種情緒用第一個參考音頻）。想挑其他輪數再用 WebUI 的 1C 試聽。

batch size 主要影響速度，對效果影響很小。影響效果的主要是資料品質、GPT 輪數和參考音頻。

預計時間：1–2 小時。

### 訓練結果

2026-10-05 用 `train_freminet.ipynb` 訓練，參數照上面的方案（batch size 2）。

| 步驟 | 時間 | 結果 |
|---|---|---|
| 1A 資料格式化 | 約 4 分鐘 | 353 段全部處理完 |
| SoVITS 8 輪 | 每輪約 5 分鐘 | `Freminet_e4_s700.pth`、`Freminet_e8_s1400.pth` |
| GPT 15 輪 | 每輪約 1 分鐘 | `Freminet-e5.ckpt`、`Freminet-e10.ckpt`、`Freminet-e15.ckpt`；GPT 訓練時去掉了 18 段語速太快或太慢的音頻，實際用 335 段 |

- 已匯出到 `Models/Freminet/`：SoVITS 第 8 輪 + GPT 第 10 輪（原本用第 15 輪，聊天時常吞字，2026-10-05 換成第 10 輪；第 15 輪的檔案還留在資料夾裏）
- GPT 第 15 輪的 top-3 準確率是 0.88，可能有點過擬合；亂念或吞字的話改試第 10 輪
- 其他輪數的模型還在 GPT-SoVITS 目錄的 `SoVITS_weights_v2ProPlus/`、`GPT_weights_v2ProPlus/`

### 打字試聽（不用 WebUI）

```
python scripts/tts.py
```

- 自動在背景啟動 GPT-SoVITS 的 `api_v2.py`，載入 `Models/Freminet/` 的模型（第一句約 30 秒，之後每句幾秒）
- 打一句按 Enter 就念出來，音頻存在 `tts_output/`（不放進 git）
- 不用 WebUI 也能挑模型和參考音頻：

  | 指令 | 作用 |
  |---|---|
  | `/angry 文字`、`/生氣 文字` | 用某種情緒念 |
  | `/gpt`、`/gpt e10` | 列出 GPT 模型／換成第 10 輪 |
  | `/sovits`、`/sovits e4` | 列出 SoVITS 模型／換成第 4 輪 |
  | `/ref`、`/ref angry`、`/ref angry 2` | 顯示目前的參考音頻／列出生氣組候選／改用第 2 段 |
  | `/help` | 說明 |

- 輸入 `q` 離開，會顯示目前選的輪數和每種情緒的參考音頻（方便填回 notebook 第 8 部分），並關掉 API
- 只用 Python 標準庫，播放用 `winsound`，所以只能在 Windows 用

### 聊天視窗

```
python scripts/chatbox.py
```

- 打字按 Enter 就用菲米尼的聲音念出來，用 `Models/Freminet/` 匯出的模型（目前 GPT e10 + SoVITS e8）
- 句子前面加情緒：`（生氣）你怎么能这样！`，也可以用 `(angry)` 或 `/angry`；不加就是平靜
- 關掉視窗會一併關掉 API

### 出問題時

| 問題 | 解決方法 |
|---|---|
| 爆顯存（OOM） | ① batch size 調成 1 → ② 去掉超過 30 秒的 5 段長音頻 → ③ 改用 v2Pro |
| 聲音不像 | 換參考音頻，或 SoVITS 多訓練幾輪 |
| 亂念、重複、吞字 | `tts.synthesize` 會逐句合成，某句比這段參考音頻平常的語速快 25% 以上（或每字短於 0.2 秒）就重念，最多 3 次。每段參考音頻語速差很多（sad 每字約 0.37 秒，calm 約 0.27 秒），所以按參考音頻記住最近 30 句的語速。少於 8 個字的短句併到下一句（「那個，好的。」常常只念出「那個」，後面變靜音）；「…」念的時候換成逗號；結巴「我…我」只念一個「我」（字幕不變）。還是常吞字的話換用輪數比較少的 GPT 模型 |
| 訓練中途被停止（記憶體不足） | 關掉瀏覽器等程式再重跑；SoVITS 會從最近保存的輪數接着訓練。SoVITS 讀資料固定用 5 個程序（寫死在整合包的 `s2_train.py`），GPT 在 notebook 裏已調成 1 個 |
| `No module named 'text'` | 整合包搬過位置，`runtime\Lib\site-packages\users.pth` 還是舊路徑；notebook 會自動修正，或者開一次 WebUI |
| 雜音、電音 | 換其他輪數的 SoVITS 模型，或換參考音頻 |

## 聊天 App

```
python scripts/app.py
```

打開 http://127.0.0.1:5000 。

**平時用：雙擊 `Freminet Chat.exe`**。會順便開 Ollama（用本地模型時），沒有黑色視窗，直接開一個聊天大小的視窗（Edge 的 app 模式，沒有分頁和網址列，可以自己拉大小），模型載入時先顯示「菲米尼正在準備…」，好了自動換成聊天畫面；關掉視窗就會關掉伺服器和語音模型，給朋友的版本連自帶的 Ollama 也一起關（聊天畫面每 20 秒告訴伺服器視窗還開着，不看 Edge 程序，因為 Edge 關了視窗可能還留在背景）。已經開着時再雙擊 exe，會多開一個視窗。
- exe 不放進 git，用 `build_exe.bat` 做（會裝 PyInstaller，圖示用 `characters/freminet.jpg`）。exe 要放在專案資料夾裏，電腦要有 Python（在 PATH 裏）
- 程式輸出記在 `app.log`；出錯會跳出提示
- 視窗大小改 `scripts/app.py` 的 `WINDOW_SIZE`；選過的背景記在 `%LOCALAPPDATA%\FreminetChat\edge`

啟動時先載入語音模型，再各送一句測試給語音模型和 LLM 預熱（不會記進聊天記錄），全部完成才換成聊天畫面，打開就能直接聊。類似 WhatsApp：打開就是和菲米尼的聊天（鋪滿整個視窗，沒有好友列表），傳訊息，他用語音訊息回覆；按播放時，語音下面會跟着進度顯示字幕。

| 檔案 | 作用 |
|---|---|
| `characters/freminet.jpg` | 頭像，從 `freminet profile/images.jpg` 裁出臉部。官方立繪有版權，不放進 git；沒有這張圖就顯示「菲」字 |
| `freminet profile/Background/` | 聊天背景圖，放進去的圖都會出現在設定裏。預設用 `background.png`。一樣不放進 git；資料夾沒有圖就用原本的底色 |
| `characters/freminet-peek.gif` | 從輸入欄後面探頭的菲米尼，從 `freminet profile/interactive asset/freminet-no-bg-sharp-2x.gif` 複製。不放進 git；沒有就不出現 |
| `characters/freminet-cursor.png` | 跟着滑鼠的小菲米尼，從 `freminet profile/cursor/chibi-character-4x.png` 切掉透明邊、縮成 128px 寬。不放進 git；沒有就不出現 |
| `characters/freminet-cursor-click.png`、`freminet-cursor-text.png` | 滑鼠指着可以點的東西 / 輸入欄時換成這兩張，從 `freminet profile/cursor/` 的 `hug-character-4x.png`（抱佩伊）和 `book-character-4x.png`（拿書）縮成 128px 寬。不放進 git；沒有就一直用上面那張 |
| `characters/freminet-heart.png` | 點他飄出來的愛心，從 `freminet profile/interactive asset/Pixel Heart Sprite Sheet 32x32.png` 複製。不放進 git |
| `config/llm.json` | 用哪個 LLM。現在用 `ollama_8b`（這部的 8b）；`ollama`（4b）、`server`（另一部電腦的 14b，不用了）也還在 |
| `config/tts.json` | GPT-SoVITS 整合包的路徑，每部電腦不同。路徑用 `/` 分隔 |
| `characters/freminet.md` | 角色資料，每則訊息都會整份放進系統提示。改完不用重開 app，下一則訊息就會用新的 |
| `scripts/llm.py` | 呼叫 LLM，用 Ollama 的 OpenAI 格式介面 |
| `scripts/app.py` | 伺服器：LLM 回覆 → 拆出情緒 → GPT-SoVITS 念出來 |
| `app/index.html` | 聊天介面 |
| `app/cursors/` | 自己畫的鼠標（SVG，32×32）：`normal` 冰藍箭頭、`click` 金色箭頭加齒輪、`text` 深藍 I 字。在 `app/index.html` 開頭的 `--cur-*` 設定，後面的數字是點擊位置 |
| `app/loading.html` | exe 打開時，模型還在載入的畫面 |
| `scripts/launcher.py` | `Freminet Chat.exe` 的程式：用本地模型時先開 Ollama，再在背景跑 `app.py --window`；給朋友的版本關視窗時會關掉自己開的 Ollama |
| `chats/` | 聊天記錄（不放進 git）；介面右上角垃圾桶可以清除，連摘要和語音檔一起清 |
| `chats/<角色>.memory.json` | 舊對話的記憶：`facts` 對方的資料、`summary` 聊過的話題，和 `upto`（記憶包括到第幾則訊息） |

- **介面右上角**（由左到右）：
  - ⚙ 聊天背景：小窗裏用左右箭頭或滑鼠滾輪切換，外面的背景即時跟着換；可以下載目前這張，或上傳新圖（存進 `freminet profile/Background/`，同名會自動改名）。可以一次選多張上傳，不合要求的會跳過（滑鼠停在失敗訊息上看原因）。上傳只收 JPG / JPEG / PNG，長和寬都至少要和視窗一樣（860×860），鋪滿時才不會拉大變模糊；改了 `WINDOW_SIZE` 的話，`app/index.html` 上傳按鈕的提示也要改。「刪除」會把目前這張從資料夾真的刪掉（要按兩次確認），刪完顯示下一張。選過的那張記在視窗的設定資料夾裏
  - 👁 隱藏聊天記錄：拿掉暗色那層，只看背景圖，再按一次回來
  - 🗑 清除聊天記錄
- **下載語音**：每則語音訊息的波形右邊有下載按鈕，存成 `菲米尼-<時間>.wav`（檔案本身在 `tts_output/`）
- **語音只留最近 50 則**（`scripts/app.py` 的 `KEEP_VOICES`，約 25MB）：每多一則就刪掉最舊那則的 wav，那則只剩文字、播放鍵變灰。視窗沒重開的話，剛被刪的那則看起來還能播，但按了沒聲音
- **鼠標**：聊天視窗裏換成 `app/cursors/` 的三個鼠標（一般 / 可以點 / 打字），離開視窗就是系統原本的
- **跟着滑鼠的菲米尼**：在滑鼠右下角，慢半拍追上去，不擋點擊；滑鼠離開視窗就淡出。指着按鈕這類可以點的東西時換成抱佩伊，指着輸入欄時換成拿書，並移到滑鼠右上角，不擋住打的字。大小改 `app/index.html` 裏 `.buddy` 的 `width`
- **探頭的菲米尼**：每隔 3–9 秒在輸入欄上面隨機位置出現，待 2.5–5 秒縮回去；點他會馬上躲起來並飄出愛心。大小改 `app/index.html` 裏 `.peek` 的 `width`（改大的話 `.hole` 的 `height` 也要加）
- 角色的圖片設定在 `scripts/app.py` 的 `FRIENDS`：`image` 頭像、`backgrounds` 背景資料夾、`background` 預設背景、`peek` 探頭 gif、`cursor` 跟着滑鼠的圖、`heart` 愛心
- **本地測試用 `qwen3:4b-instruct`**（Ollama，2.5GB）。不要用 `qwen3:4b`：它會先「思考」，Ollama 的 OpenAI 介面關不掉，回覆會變成空的
- exe 開 Ollama 時設了 `OLLAMA_KEEP_ALIVE=-1`，LLM 不會閒置 5 分鐘就被卸載（只在 exe 自己開 Ollama 時有效）
- **記憶**：原文最多傳 `history_turns` 輪（這部 8 輪，server 12 輪）。超過了就把較舊的一半整理進記憶，放在系統提示最後，原文只留最近一半。記憶分兩份：
  - 一次砍一半，不是每則訊息去掉一輪，這樣傳給 LLM 的內容幾則訊息內都不變，Ollama 的快取能命中
  - 摘要在回覆送出後於背景整理；聊天記錄本身不會刪，介面還是看得到全部
  - **對方的資料**（`facts`）：名字、寵物、生日、工作、喜好這類，只從對方傳的訊息裏找，每條只根據一則訊息（試過把「生日」和「下個月去旅行」拼成「生日是下個月」），只加不刪（重複的由程式用 `similar` 跳過），超過 `MAX_FACTS`（400 字）才請 LLM 合併。以前和話題混在一份摘要裏，聊 48 輪後名字、貓、生日全被當成舊的刪掉
  - **摘要**（`summary`）：聊過的話題、約定、心情，300 字以內，舊的會慢慢擠掉。不准寫個人資料、不准推測（試過它自己編了一個生日）
  - 系統提示最後有「記憶」一段：資料和摘要裏有的要肯定回答；都沒有的就是「聽過但忘了」，用自己的話承認、請對方再說，不要猜。每則訊息隨機給一個合角色的說法方向（`FORGET_STYLES`），不寫固定例句，連他自己說過的句子也不能放進提示，不然照抄
  - 2026-10-10 用模擬長聊天測（說 8 個細節、閒聊 40 輪、再問 8 個說過的和 8 個沒說過的）：說過的 5–8/8 答對（之前 0/8），沒說過的不會編答案；但 8b 說「忘了」時幾乎每次都套同一個句型，試過叫它避開、重寫最多 3 次都沒用，所以沒留重寫
  - 結巴（「我…我」）：最近兩則用過就自動拿掉（`calm`），角色設定說只在真的緊張時用
  - Ollama 的上下文只有 4096 token：角色資料 + 摘要 + 4 輪約 3100，最多 8 輪時大約接近上限；角色資料再加長的話要調低 `history_turns`
- 和 GPT-SoVITS 一起用大約佔 5.5GB 顯存
- 速度：啟動（載入 + 預熱）約 1–2 分鐘；打開後短回覆約 5 秒，5 句左右的長回覆約 13 秒（逐句合成，吞字還要重念）
- 模型回覆第一行是情緒標籤（例如 `[shy]`），用來選參考音頻；（笑）、*低頭* 這類動作描寫會自動拿掉，不會念出來
- 小模型的毛病，提示裏禁不掉，所以在程式裏處理：
  - 回覆夾英文（`maybe`、`usually`）就重新生成，最多 3 次。對方說要「英文 / 英語 / English」，或整則訊息都是英文時才放行；中文裏夾個「LOL」不算。整句英文的語音用英文模式念（模型只用中文配音訓練，口音可能不好）
  - 回覆太長（像念稿）：提示要求一兩句、三十字左右，超過 45 字（`MAX_CHARS`，英文一個單字算兩字）就在句子結尾切掉
  - 最近兩句已經用「那個…」「嗯…」這類語氣詞開頭的話，這句開頭的語氣詞會去掉，不會每句都「那個…」
- **用另一部電腦的模型**：見 [LLM 伺服器](#llm-伺服器)，把 `active` 改成 `server`
- `no_think`：傳 `reasoning_effort: "none"`，`qwen3:14b` 這類混合模型就不會先「思考」把回覆字數用完。實測在提示寫 `/no_think` 沒用；`qwen3:4b`（現在是 2507 只會思考的版本）怎樣都關不掉

## 聊天程式的規劃

開始寫 app 前的規劃，每項後面註明現在的狀況。

### 架構

```
輸入文字 → LLM（生成 Freminet 的回覆和情緒）→ 本地 GPT-SoVITS api_v2.py（逐句念出來）→ 語音訊息
```

### LLM

- 2026-10-07 本來決定只用本地模型，之後重新比較本地和 API，見[比較簡報](https://claude.ai/artifact/C4JQrqPKo8T9QSAaTbEwWc)。還沒決定
- 這部電腦的 6GB 顯存要留給 GPT-SoVITS，所以 LLM 放在另一部電腦（RTX 5060 Laptop 8GB、16GB 記憶體）跑 `qwen3:14b`
  - 14B 角色扮演算及格：聊久了可能忘記角色、對原神設定知道得少
  - 想更好：記憶體加到 32GB，換 30B-A3B 這類 MoE 模型
- 這部電腦的 `qwen3:4b-instruct` 和 `qwen3:8b` 留着做測試。8b 在這部會有大約 17% 放在 CPU 跑（顯存要分給 GPT-SoVITS），短回覆約 2–4 秒
- 8b 的限制：緊張時結巴偏多、偶爾夾英文、很愛照抄提示裏的範例內容（範例寫「看到幽光星星」，他每次都說這句）
- 角色像不像主要看提示詞，寫在 `characters/freminet.md`

### LLM 伺服器

那部電腦只要 `server/` 的兩個 notebook，用 VS Code 打開，由上而下按 ▶ 執行。

前置條件：Windows 10/11、管理員帳號、C 槽 12GB 以上；電源設成插電時不睡眠。裝好 Python，VS Code 裝好 Python 和 Jupyter 擴充功能。在 PowerShell 執行 `irm https://ollama.com/install.ps1 | iex` 裝 Ollama，裝好後重開 VS Code。和聊天電腦同一個網絡，或者兩部都裝 Tailscale（見下面）。

| 檔案 | 做什麼 | 什麼時候跑 |
|---|---|---|
| `install_server.ipynb` | 下載 `qwen3:14b`（約 9GB）、開防火牆（會彈出管理員視窗，按「是」）。沒裝 Ollama 的話會提示先裝 | 第一次 |
| `start_server.ipynb` | 開伺服器：顯示 IP、載入模型、測試一句，然後一直運行；按 ■ 停止 | 每次 |

想換模型改兩個檔案 cell 1 的 `MODEL`（兩個要一樣）。

- Ollama 裝在其他磁碟也可以：程式先從 PATH 找，找不到才看預設位置；cell 1 會印出找到的位置。剛裝完要重開 VS Code 才讀到新的 PATH
- 模型預設存在 C 槽（`C:\Users\<你>\.ollama\models`），就算 Ollama 裝在 D 槽也一樣
- 防火牆只要開一次，重開機不會消失；重新安裝 Ollama 到不同位置才要再開

這部電腦的 `config/llm.json`：`server.base_url` 填那部的 IP，`active` 改成 `server`（只改一次）。

之後每次：先在那部跑 `start_server.ipynb`，再開這部的 `Freminet Chat.exe`。順序反了的話 LLM 預熱會失敗，第一則訊息要多等十幾秒載入。

- 防火牆規則只讓同一個網絡和 Tailscale（`100.64.0.0/10`）的電腦連入，不分私人／公用網絡（Windows 新連的 Wi-Fi 預設是公用）
- **直接關掉 VS Code 伺服器不會停**：要停就按 `start_server.ipynb` 開伺服器那格的 ■
- **Ollama 沒有密碼**：同一個 Wi-Fi 的人都能用模型、刪模型、看到聊天內容（沒加密）。只在家裏開，公共 Wi-Fi 不要開伺服器
- 路由器重開後 IP 可能會變，連不上就看 `start_server.ipynb` 顯示的 IP；想固定的話在路由器設 DHCP 保留，或者用 Tailscale 的 IP
- Ollama 的記錄在 `%TEMP%\ollama_server.log`
- 在這部電腦測過（用 `qwen3:4b-instruct`）：下載模型、開伺服器、停止。還沒驗證：開防火牆（要管理員）、14B 的速度、Tailscale 實際連線

**兩部電腦不在同一個地方：用 Tailscale**

1. 兩部電腦都到 https://tailscale.com/download 裝 Tailscale，登入**同一個帳號**
2. `start_server.ipynb` 會多顯示一行 Tailscale IP（`100.x.x.x`），填到 `server.base_url`。這個 IP 不會變，在家裏也可以一直用它

每次用的時候，兩部電腦的 Tailscale 都要開着並顯示 Connected（預設開機自動啟動）。

每部電腦在 Tailscale 都有自己的 IP，`base_url` 要填 **server 的**，不是聊天電腦自己的。登入同一個帳號就會自動加入，不用另外加裝置。

有加密，只有登入你帳號的裝置連得到。**不要在路由器開端口轉發**：Ollama 沒有密碼，開了全世界都能用。

### 速度

- ~~邊生成邊播放~~：改成語音訊息的設計，整則念好才出現，所以沒有做
- GPT-SoVITS 用 `api_v2.py`，模型常駐、開半精度
- 還是太慢才考慮雲端 GPU（AutoDL、RunPod、Vast.ai、Modal）

### 注意

這是配音員的真實聲音，只用於個人和同人用途，不要商用，也不要用來冒充本人。
