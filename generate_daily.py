import os
import json
import io
import re
import datetime
import requests
from google import genai
from gtts import gTTS
from pydub import AudioSegment

# 1. 初期化
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# 2. 対象フォルダ内の「製図 音声解説ソース」を自動検索して取得
FOLDER_ID = "1czW_J-e83J_FdorXYqyCJsjYuKNxD8cl"
TARGET_DOC_NAME = "製図 音声解説ソース"

print(f"① Googleドライブのフォルダ内を検索中...")
folder_url = f"https://drive.google.com/embeddedfolderview?id={FOLDER_ID}#list"

target_file_id = None
try:
    res = requests.get(folder_url)
    if res.status_code == 200:
        # フォルダ内HTMLから「製図 音声解説ソース」のIDを抽出
        # 形式例: ['ID', '製図 音声解説ソース']
        pattern = rf'\["([a-zA-Z0-9_-]{{25,}})",\s*"{re.escape(TARGET_DOC_NAME)}"'
        match = re.search(pattern, res.text)
        if match:
            target_file_id = match.group(1)
            print(f"最新の「{TARGET_DOC_NAME}」を検出しました。")
        else:
            print(f"完全一致する「{TARGET_DOC_NAME}」が見つかりませんでした。旧版と区別して再検索します。")
            # 汎用検索：title属性やリンクから抽出
            alt_pattern = rf'/document/d/([a-zA-Z0-9_-]+)/edit[^>]*>{re.escape(TARGET_DOC_NAME)}<'
            alt_match = re.search(alt_pattern, res.text)
            if alt_match:
                target_file_id = alt_match.group(1)
                print(f"最新の「{TARGET_DOC_NAME}」を検出しました。")
except Exception as e:
    print(f"フォルダ検索エラー: {e}")

source_content = "本日の学習記録はありません。"

if target_file_id:
    export_url = f"https://docs.google.com/document/d/{target_file_id}/export?format=txt"
    doc_res = requests.get(export_url)
    if doc_res.status_code == 200:
        source_content = doc_res.text
        print(f"ドキュメント本文の取得に成功しました（{len(source_content)} 文字）")
    else:
        print(f"ドキュメントのダウンロードに失敗しました (Status: {doc_res.status_code})")
else:
    print("有効なドキュメントが見つからなかったため、おさらいモードで動作します。")

# 3. 指定プロンプトでGeminiに台本生成を依頼
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
    config={"response_mime_type": "application/json
