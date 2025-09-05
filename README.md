# Stable Diffusion WebUI 拡張機能 – 自動画像POST

この拡張機能は **Stable Diffusion WebUI** で生成された画像を、自動的に外部サーバへ送信（POST）します。  
画像は **data URL形式（Base64埋め込み）** に変換され、非同期処理でサーバへ送信されるため、生成速度には影響しません。  


## ✨ 特徴

- **完全自動**: 生成された画像は保存と同時に外部サーバへ送信  
- **非同期処理**: バックグラウンドスレッドで動作し、UI操作を妨げない  
- **リトライ＆タイムアウト**: HTTPリトライとタイムアウトを設定可能  
- **WebUIから設定可能**: サーバURL・APIパス・FolderID・トークンなどをUIで切り替え  


## ⚙️ WebUI 設定項目

拡張機能を導入すると、WebUI の **Settings → Image Send Info** に以下の設定が追加されます。

| UIラベル                         | 入力例                              | 説明 |
|----------------------------------|-------------------------------------|------|
| Send all images                  | true / false                        | ONにすると送信が有効になります |
| Outside server base URL          | https://example.com:8443           | 送信先サーバのURL |
| API path                         | /api/item/addFromURL                | サーバ側の受信エンドポイント |
| FolderID                         | album001                            | 保存時のフォルダ識別子 |
| Auth Token (X-Auth-Token)        | my-secret                           | 任意。送信時にヘッダ `X-Auth-Token` を追加 |
| Request timeout (seconds)        | 10                                  | タイムアウト秒数 |
| HTTP max retries on failure      | 3                                   | リトライ回数 |

---

## 🔄 動作概要

1. `script_callbacks.on_image_saved` をフック  
2. 保存された画像を **Base64エンコード** し、`data:<mime>;base64,...` 形式に変換  
3. 下記の形式でサーバへPOST  

```json
{
  "url": "data:image/png;base64,iVBORw0KGgoAAA...",
  "name": "test-image",
  "folderId": "album001"
}
```

サーバは POST /api/item/addFromURL （デフォルト）を受け取り、画像を保存

## 🌐 サーバ側の期待仕様

```text
・メソッド: POST

・パス: ${BASE_URL}${API_PATH} （例: https://example.com:8443/api/item/addFromURL）

・ヘッダ:

Content-Type: application/json
X-Auth-Token（設定した場合のみ）

・ボディ(JSON):

url: data URL文字列
name: ファイル名（拡張子なし）
folderId: フォルダ識別子
```

## 🛠️ 動作確認コマンド（サーバテスト用）

```text
curl -X POST "https://example.com:8443/api/item/addFromURL" \
  -H "Content-Type: application/json" \
  -H "X-Auth-Token: my-secret" \
  -d '{
    "url": "data:image/png;base64,iVBORw0KGgoAAA...",
    "name": "test-image",
    "folderId": "album001"
  }'
```

## ✅ 利用手順まとめ

1. extensions/ に sdweb-image-send を配置
2. WebUIを再起動
3. Settings → Image Send Info を開いて設定
- Send all images → ON
- Outside server base URL → 例: https://example.com:8443
- API path → /api/item/addFromURL
- FolderID → album001
- 必要に応じて Auth Token, Timeout, Retries を設定

4. 画像を生成すると自動送信されます

## 🔒 セキュリティ注意点

- 公開APIの場合は Auth Token必須 を推奨
- HTTPSを利用してください
- サーバ側では name・folderId の検証を行い、不正入力を防ぐこと

## 🐞 トラブルシューティング

- 送信されない
  - Send all images がONか確認
  - Base URLとAPI Pathが正しいか確認
  - FolderIDが空でないか確認

- タイムアウト/5xx
  - Timeout秒数やRetriesを増やす
  - サーバ側のログを確認
- デバッグ出力
   - ソース冒頭の DEBUG = False を True に変更するとログが出力されます

## ❓ FAQ

Q. 生成が遅くなりますか？  
→ いいえ。送信処理はスレッドで非同期実行されます。

Q. APIパスは固定ですか？  
→ 設定画面の「API path」で自由に変更できます。


## 📝 更新履歴

v1.0.0: 初版リリース      
 – 非同期送信、リトライ・タイムアウト対応、設定画面から切替可能

