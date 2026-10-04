# Freminet 語音聊天機器人

目標：用 Freminet（菲米尼）的中文語音訓練一個 GPT-SoVITS 語音模型，之後再接上 LLM，做一個可以和角色對話、並用他的聲音回覆的聊天程式。

## 目前進度

- [x] 下載 Freminet 中文語音資料
- [x] 整理成 GPT-SoVITS 訓練格式（`freminet.list`）
- [ ] 訓練語音模型（v2ProPlus，本地）
- [ ] 挑選參考音頻
- [ ] 寫角色提示詞（從官方台詞挑範例）
- [ ] 寫聊天程式（LLM API + GPT-SoVITS）

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

batch size 主要影響速度，對效果影響很小。影響效果的主要是資料品質、GPT 輪數和參考音頻。

預計時間：1–2 小時。

### 出問題時

| 問題 | 解決方法 |
|---|---|
| 爆顯存（OOM） | ① batch size 調成 1 → ② 去掉超過 30 秒的 5 段長音頻 → ③ 改用 v2Pro |
| 聲音不像 | 換參考音頻，或 SoVITS 多訓練幾輪 |
| 亂念、重複、吞字 | 換用輪數比較少的 GPT 模型 |
| 雜音、電音 | 換其他輪數的 SoVITS 模型，或換參考音頻 |

## 之後：聊天程式（語音訓練完再做）

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
