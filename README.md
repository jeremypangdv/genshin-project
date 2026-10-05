# Freminet 語音聊天機器人

目標：用 Freminet（菲米尼）的中文語音訓練一個 GPT-SoVITS 語音模型，之後再接上 LLM，做一個可以和角色對話、並用他的聲音回覆的聊天程式。

## 目前進度

- [x] 下載 Freminet 中文語音資料
- [x] 整理成 GPT-SoVITS 訓練格式（`freminet.list`）
- [x] 訓練語音模型（v2ProPlus，本地，2026-10-05，見[訓練結果](#訓練結果)）
- [ ] 挑選參考音頻（已按情緒選好 37 段候選，還要試聽確定每種情緒用哪段）
- [ ] 試聽模型，確定用哪個輪數（**目前在做**，用 `python scripts/tts.py`）
  1. GPT：用同一句話試 e5、e10、e15，選最好的（`/gpt e10`）
  2. SoVITS：用選好的 GPT，試 e4、e8，選最好的（`/sovits e4`）
  3. 最好的 GPT + 最好的 SoVITS 一起用，填回 notebook 第 8 部分重新匯出
- [x] 寫角色資料：`characters/freminet.md`（bilibili wiki + 353 句官方語音整理：身世、個性、喜好、佩伊、對其他角色的看法、台詞範例）
- [x] 寫聊天程式（LLM + GPT-SoVITS）：`python scripts/app.py`，見[聊天 App](#聊天-app)
- [ ] 換成 API（DeepSeek / Claude）調整角色效果

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

- 顯卡：RTX 3060 Laptop，**6GB 顯存**
- 記憶體：16GB
- GPT-SoVITS：`D:\characters\GPT-SoVITS-Rin\GPT-SoVITS-v2pro-20250604`（2025-06 整合包，v2Pro / v2ProPlus / v4 底模都已齊全，不用下載）

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

- 已匯出到 `Models/Freminet/`：SoVITS 第 8 輪 + GPT 第 15 輪
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

- 打字按 Enter 就用菲米尼的聲音念出來，用 `Models/Freminet/` 匯出的模型（目前 GPT e15 + SoVITS e8）
- 句子前面加情緒：`（生氣）你怎么能这样！`，也可以用 `(angry)` 或 `/angry`；不加就是平靜
- 關掉視窗會一併關掉 API

### 出問題時

| 問題 | 解決方法 |
|---|---|
| 爆顯存（OOM） | ① batch size 調成 1 → ② 去掉超過 30 秒的 5 段長音頻 → ③ 改用 v2Pro |
| 聲音不像 | 換參考音頻，或 SoVITS 多訓練幾輪 |
| 亂念、重複、吞字 | 換用輪數比較少的 GPT 模型 |
| 訓練中途被停止（記憶體不足） | 關掉瀏覽器等程式再重跑；SoVITS 會從最近保存的輪數接着訓練。SoVITS 讀資料固定用 5 個程序（寫死在整合包的 `s2_train.py`），GPT 在 notebook 裏已調成 1 個 |
| `No module named 'text'` | 整合包搬過位置，`runtime\Lib\site-packages\users.pth` 還是舊路徑；notebook 會自動修正，或者開一次 WebUI |
| 雜音、電音 | 換其他輪數的 SoVITS 模型，或換參考音頻 |

## 聊天 App

```
python scripts/app.py
```

打開 http://127.0.0.1:5000 。類似 WhatsApp：左邊點「菲米尼」，傳訊息，他用語音訊息回覆；按播放時，語音下面會跟着進度顯示字幕。

| 檔案 | 作用 |
|---|---|
| `config/llm.json` | 用哪個 LLM。改 `active` 就能換：`ollama`（本地測試）、`deepseek`、`claude` |
| `characters/freminet.md` | 角色資料，每則訊息都會整份放進系統提示。改完不用重開 app，下一則訊息就會用新的 |
| `scripts/llm.py` | 呼叫 LLM，三個都用 OpenAI 格式的介面 |
| `scripts/app.py` | 伺服器：LLM 回覆 → 拆出情緒 → GPT-SoVITS 念出來 |
| `app/index.html` | 聊天介面 |
| `chats/` | 聊天記錄（不放進 git）；介面右上角垃圾桶可以清除 |

- **本地測試用 `qwen3:4b-instruct`**（Ollama，2.5GB）。不要用 `qwen3:4b`：它會先「思考」，Ollama 的 OpenAI 介面關不掉，回覆會變成空的
- Ollama 的上下文只有 4096 token，角色資料約佔 2400，所以 `ollama` 只記住最近 8 輪（`history_turns`）；角色資料再加長的話要再調低
- 和 GPT-SoVITS 一起用大約佔 5.5GB 顯存；第一則訊息約 30 秒，之後每則約 5 秒
- 模型回覆第一行是情緒標籤（例如 `[shy]`），用來選參考音頻；（笑）、*低頭* 這類動作描寫會自動拿掉，不會念出來
- 換 API：設定環境變數 `DEEPSEEK_API_KEY` 或 `ANTHROPIC_API_KEY`，再把 `active` 改成 `deepseek` 或 `claude`
- 小模型只用來測流程，角色像不像要換成 API 之後再調

## 聊天程式的規劃

### 架構

```
輸入文字 → LLM API（生成 Freminet 的回覆）→ 本地 GPT-SoVITS api_v2.py（念出來）→ 播放
```

### LLM

- **用 API，不用本地模型**：6GB 顯存要留給 GPT-SoVITS，本地小模型角色扮演效果不好
- 選項：
  - **Claude Sonnet 5.5**：角色最穩定，effort 設 `low`，開 prompt caching
  - **DeepSeek**：便宜，中文好，可以先用來開發測試
- 角色像不像主要看提示詞：從 353 句官方台詞挑一些作為說話風格範例

### 控制花費

- 只充少量金額（例如 $5），**不要開自動充值**
- 在 Console 設每月花費上限
- 程式裏限制 `max_tokens`、統計花費，超過上限自動停止
- 開發時先用假的回覆測試整個流程，確定沒問題再接真 API

### 速度

- **邊生成邊播放**：LLM 串流輸出，每完成一句就送去 GPT-SoVITS，第一句生成好就開始播放
- GPT-SoVITS 用 `api_v2.py`，模型常駐、開半精度
- 還是太慢才考慮雲端 GPU（AutoDL、RunPod、Vast.ai、Modal）

### 注意

這是配音員的真實聲音，只用於個人和同人用途，不要商用，也不要用來冒充本人。
