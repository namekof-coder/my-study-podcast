import os
import json
import io
import datetime
import requests
from google import genai
from gtts import gTTS
from pydub import AudioSegment

# 1. Geminiクライアントの初期化（GitHub Secretsからキーを取得）
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# 2. Googleドキュメントの最新内容を自動取得（Web公開テキスト形式）
DOC_ID = "1feUPZWIaEh3wiOn1FolKatyHBDmIXy9wKmqPU0yilaI"
DOC_EXPORT_URL = f"https://docs.google.com/document/d/{DOC_ID}/export?format=txt"

print("① Googleドキュメントから最新の学習記録を取得中...")
res_doc = requests.get(DOC_EXPORT_URL)
if res_doc.status_code == 200:
    source_content = res_doc.text
    print(f"取得成功（{len(source_content)} 文字）")
else:
    print(f"ドキュメント取得に失敗しました (Status: {res_doc.status_code})。フォールバックします。")
    source_content = "本日の学習記録はありません。"

# 3. 指定のプロンプトでGeminiに台本を依頼
prompt = f"""
あなたは一級建築士 設計製図試験の講師です。以下の「製図 音声解説ソース」をもとに、音声解説（Audio Overview）台本を作成してください。

=== 製図 音声解説ソース ===
{source_content}
===========================

【聞き手】
実務経験13年の二級建築士で、一級建築士の設計製図試験を受験予定。課題文の読み取りと、計画の要点の記述を強化中。育児の合間に聞くので、耳だけで理解できる構成にする。

【言葉選び】
・建築の基礎用語（スパン、竪穴区画、EXP.J、延焼のおそれのある部分など）は説明なしで使ってよい
・法令や基準の数値は「令第120条で50m」のように根拠とセットで話す
・ソースに書かれていないことは断定せず、「資格学校の教材で確認を」と添える

【構成（合計10分程度、日本語、2人の対話形式）】
1. オープニング（30秒）：今日の日付と、取り組んだ問題数・結果をひとことで
2. 今日のひとこと（1〜2分）：最新動向を紹介。公式発表（確定）か、資格学校の分析・予想かを必ず区別する
3. 今日の問題の振り返り（5〜6分）：1問ずつ
   ・問題の要旨（前提の用途も）
   ・本人がどう答えたか
   ・正誤と、なぜそうなるのか
   ・本番の計画の要点や作図でどう活かすか
   ・間違えた問題と、評価が△・×の記述に時間を多く使う。正解した問題は短く
4. 深掘り（1〜2分）：今日の内容から試験で狙われやすい知識を1つ選んで掘り下げる
5. まとめ（30秒）：明日までに思い出したい復習ポイントを3つ

【トーン】
本人の解答を頭ごなしに否定せず、「ここまでは拾えている、次はここを足す」という具体的な言い方にする。

【学習記録がない日】
「今日は学習記録なし」と伝えたうえで、ソースにあるおさらい問題を使って5分程度の復習回にする。

【出力フォーマット】
講師（Koushi）と受講生・ナビゲーター（Navi）の2人の対話として、必ず以下のJSON配列のみを出力してください（Markdown記号やバッククォート等も不要です）：
[
  {{"speaker": "Koushi", "text": "皆さん、おはようございます！一級建築士設計製図の音声解説です。"}},
  {{"speaker": "Navi", "text": "おはようございます！今日もよろしくお願いします。"}}
]
"""

print("② Geminiが台本を作成中...")
response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=prompt,
    config={"response_mime_type": "application/json"}
)

dialogue = json.loads(response.text)
print(f"台本が完成しました（全{len(dialogue)}セリフ）")

# 4. 音声合成と結合
print("③ クラウド音声合成中...")
combined_audio = AudioSegment.empty()
pause = AudioSegment.silent(duration=350)

for i, item in enumerate(dialogue):
    speaker = item["speaker"]
    text = item["text"]
    
    # 講師と受講生でアクセント・ドメインを切り替えて声色を分ける
    tld = "co.jp" if speaker == "Koushi" else "com"
    tts = gTTS(text=text, lang="ja", tld=tld)
    
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    
    segment = AudioSegment.from_file(fp, format="mp3")
    combined_audio += segment + pause

output_audio = "daily_overview.mp3"
combined_audio.export(output_audio, format="mp3")
file_size = os.path.getsize(output_audio)
print(f"音声ファイル保存完了: {output_audio} ({file_size} bytes)")

# 5. podcast.xml の自動更新
print("④ podcast.xml を更新中...")
today_str = datetime.date.today().strftime("%Y-%m-%d")
now_rfc = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%a, %d %b %Y %H:%M:%S +0900")

xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="
