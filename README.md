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
- [x] 寫角色資料：`characters/freminet.md`（bilibili wiki + 353 句官方語音整理：身世、個性、喜好、佩伊、對其他角色的看法、情緒指引、台詞範例）
- [x] 聊天 App（**可以用了**，雙擊 `start_chat.bat`，見[聊天 App](#聊天-app)）
  - 類似 WhatsApp，菲米尼用語音訊息回覆，播放時顯示字幕，頭像用他的照片
  - 他會自己選情緒（9 種），用對應的參考音頻念
  - 聊天記錄會保存；吞字會自動重念
  - 目前用本地的 `qwen3:4b-instruct` 測試
- [ ] 在另一部電腦（RTX 5060 8GB）跑 `qwen3:14b`，這部透過區域網絡連過去（**下一步**，2026-10-07 決定只用本地模型，不用 API，見 [LLM](#llm)）
  - [x] 寫好 `server/install_server.bat` 和 `server/start_server.bat`
  - [ ] 在那部電腦安裝、測試連線，再調角色效果
- [x] 長期記憶：舊對話整理成摘要（見[聊天 App](#聊天-app)）

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
- GPT-SoVITS：`D:\characters\GPT-SoVITS-Rin\GPT-SoVITS-v2pro-20250604`（2025-06 整合包，v2Pro / v2ProPlus / v4 底模都已齊全，不用下載）

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
| 亂念、重複、吞字 | `tts.synthesize` 會逐句合成，某句短於每字 0.2 秒（訓練資料最快約 0.19）就重念，最多 3 次；「…」念的時候換成逗號。還是常吞字的話換用輪數比較少的 GPT 模型 |
| 訓練中途被停止（記憶體不足） | 關掉瀏覽器等程式再重跑；SoVITS 會從最近保存的輪數接着訓練。SoVITS 讀資料固定用 5 個程序（寫死在整合包的 `s2_train.py`），GPT 在 notebook 裏已調成 1 個 |
| `No module named 'text'` | 整合包搬過位置，`runtime\Lib\site-packages\users.pth` 還是舊路徑；notebook 會自動修正，或者開一次 WebUI |
| 雜音、電音 | 換其他輪數的 SoVITS 模型，或換參考音頻 |

## 聊天 App

```
python scripts/app.py
```

打開 http://127.0.0.1:5000 。或者直接雙擊 `start_chat.bat`：會順便開 Ollama，關掉黑色視窗就會關掉伺服器。啟動時黑色視窗會先載入語音模型，再各送一句測試給語音模型和 LLM 預熱（不會記進聊天記錄），全部完成才自動打開瀏覽器，打開就能直接聊。類似 WhatsApp：左邊點「菲米尼」，傳訊息，他用語音訊息回覆；按播放時，語音下面會跟着進度顯示字幕。

| 檔案 | 作用 |
|---|---|
| `characters/freminet.jpg` | 頭像，從 `freminet profile/images.jpg` 裁出臉部。官方立繪有版權，不放進 git；沒有這張圖就顯示「菲」字 |
| `config/llm.json` | 用哪個 LLM。改 `active` 就能換：`ollama`（這部電腦）、`server`（另一部電腦） |
| `characters/freminet.md` | 角色資料，每則訊息都會整份放進系統提示。改完不用重開 app，下一則訊息就會用新的 |
| `scripts/llm.py` | 呼叫 LLM，用 Ollama 的 OpenAI 格式介面 |
| `scripts/app.py` | 伺服器：LLM 回覆 → 拆出情緒 → GPT-SoVITS 念出來 |
| `app/index.html` | 聊天介面 |
| `chats/` | 聊天記錄（不放進 git）；介面右上角垃圾桶可以清除，連摘要一起清 |
| `chats/<角色>.memory.json` | 舊對話的摘要，和 `upto`（摘要包括到第幾則訊息） |

- **本地測試用 `qwen3:4b-instruct`**（Ollama，2.5GB）。不要用 `qwen3:4b`：它會先「思考」，Ollama 的 OpenAI 介面關不掉，回覆會變成空的
- `start_chat.bat` 設了 `OLLAMA_KEEP_ALIVE=-1`，LLM 不會閒置 5 分鐘就被卸載（只在 bat 自己開 Ollama 時有效）
- **記憶**：原文最多傳 `history_turns` 輪（這部 8 輪，server 12 輪）。超過了就把較舊的一半整理成摘要（200 字以內），放在系統提示最後，原文只留最近一半。
  - 一次砍一半，不是每則訊息去掉一輪，這樣傳給 LLM 的內容幾則訊息內都不變，Ollama 的快取能命中
  - 摘要在回覆送出後於背景整理；聊天記錄本身不會刪，介面還是看得到全部
  - Ollama 的上下文只有 4096 token：角色資料 + 摘要 + 4 輪約 3100，最多 8 輪時大約接近上限；角色資料再加長的話要調低 `history_turns`
- 和 GPT-SoVITS 一起用大約佔 5.5GB 顯存
- 速度：啟動（載入 + 預熱）約 1–2 分鐘；打開後短回覆約 5 秒，5 句左右的長回覆約 13 秒（逐句合成，吞字還要重念）
- 模型回覆第一行是情緒標籤（例如 `[shy]`），用來選參考音頻；（笑）、*低頭* 這類動作描寫會自動拿掉，不會念出來
- **用另一部電腦的模型**：見 [LLM 伺服器](#llm-伺服器)，把 `active` 改成 `server`
- `no_think`：傳 `reasoning_effort: "none"`，`qwen3:14b` 這類混合模型就不會先「思考」把回覆字數用完。實測在提示寫 `/no_think` 沒用；`qwen3:4b`（現在是 2507 只會思考的版本）怎樣都關不掉

## 聊天程式的規劃

開始寫 app 前的規劃，每項後面註明現在的狀況。

### 架構

```
輸入文字 → LLM（生成 Freminet 的回覆和情緒）→ 本地 GPT-SoVITS api_v2.py（逐句念出來）→ 語音訊息
```

### LLM

- **只用本地模型，不用 API**（2026-10-07 決定）
- 這部電腦的 6GB 顯存要留給 GPT-SoVITS，所以 LLM 放在另一部電腦（RTX 5060 Laptop 8GB、16GB 記憶體）跑 `qwen3:14b`
  - 14B 角色扮演算及格：聊久了可能忘記角色、對原神設定知道得少
  - 想更好：記憶體加到 32GB，換 30B-A3B 這類 MoE 模型
- 這部電腦的 `qwen3:4b-instruct` 留着做測試
- 角色像不像主要看提示詞：已經從 353 句官方台詞挑了範例，寫在 `characters/freminet.md`

### LLM 伺服器

那部電腦只要 `server/` 的兩個檔案，不用裝 Python。從 GitHub 下載要用「Download raw file」。

前置條件：Windows 10/11、管理員帳號、C 槽 12GB 以上；電源設成插電時不睡眠。和聊天電腦同一個網絡，或者兩部都裝 Tailscale（見下面）。

1. 雙擊 `install_server.bat`（只做一次）：裝 Ollama、下載 `qwen3:14b`（約 9GB）、開防火牆 11434 端口。想換模型改檔案開頭的 `MODEL`
2. 每次用之前雙擊 `start_server.bat`：會顯示那部電腦的 IP，視窗保持開着，關掉就停止
3. 這部電腦的 `config/llm.json`：`server.base_url` 填那部的 IP，`active` 改成 `server`（只改一次）

之後每次：先開那部的 `start_server.bat`，再開這部的 `start_chat.bat`。順序反了的話 LLM 預熱會失敗，第一則訊息要多等十幾秒載入。

- 防火牆規則只讓同一個網絡和 Tailscale（`100.64.0.0/10`）的電腦連入，不分私人／公用網絡（Windows 新連的 Wi-Fi 預設是公用）
- 兩個 bat 檔只用英文：檔案裏有中文的話，cmd 會讀錯行。存進 git 時是 CRLF（`.gitattributes`），LF 的話 `goto` 可能跳錯
- **Ollama 沒有密碼**：同一個 Wi-Fi 的人都能用模型、刪模型、看到聊天內容（沒加密）。只在家裏開，公共 Wi-Fi 不要開 `start_server.bat`
- 路由器重開後 IP 可能會變，連不上就看 `start_server.bat` 顯示的 IP；想固定的話在路由器設 DHCP 保留，或者用 Tailscale 的 IP
- 還沒在那部電腦實際跑過：安裝 Ollama、管理員權限、防火牆、14B 的速度、Tailscale 都還沒驗證

**兩部電腦不在同一個地方：用 Tailscale**

1. 兩部電腦都到 https://tailscale.com/download 裝 Tailscale，登入**同一個帳號**
2. 2026-10-07 之前跑過 `install_server.bat` 的話，再跑一次（防火牆規則才有 Tailscale；Ollama 和模型已經有，會跳過）
3. `start_server.bat` 會多顯示一行 Tailscale IP（`100.x.x.x`），填到 `server.base_url`。這個 IP 不會變，在家裏也可以一直用它

有加密，只有登入你帳號的裝置連得到。**不要在路由器開端口轉發**：Ollama 沒有密碼，開了全世界都能用。

### 速度

- ~~邊生成邊播放~~：改成語音訊息的設計，整則念好才出現，所以沒有做
- GPT-SoVITS 用 `api_v2.py`，模型常駐、開半精度
- 還是太慢才考慮雲端 GPU（AutoDL、RunPod、Vast.ai、Modal）

### 注意

這是配音員的真實聲音，只用於個人和同人用途，不要商用，也不要用來冒充本人。
