#!/usr/bin/env python3
"""
使用 Azure Speech Service (付费TTS) 批量生成 Ninja Kid 句子 MP3 音频
声音: en-US-AvaMultilingualNeural (高质量多语言神经网络声音)
"""
import asyncio
import aiohttp
import os
import re
import time

AZURE_KEY = os.environ.get("AZURE_SPEECH_KEY", "YOUR_AZURE_SPEECH_KEY_HERE")
AZURE_REGION = "eastasia"
TTS_URL = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
# 使用高质量的 Ava 多语言声音
VOICE_NAME = "en-US-AvaMultilingualNeural"
OUTPUT_FORMAT = "audio-48khz-192kbitrate-mono-mp3"  # 高品质MP3

def extract_sentences_from_js(js_file):
    """读取 JS 文件并提取所有章节的句子"""
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    chapters = {}
    current_chapter = None
    sentence_index = 0
    
    for line in content.split('\n'):
        # 匹配章节号 - 支持多种缩进格式
        ch_match = re.search(r'^\s*(\d+)\s*:\s*\{', line)
        if ch_match:
            current_chapter = int(ch_match.group(1))
            chapters[current_chapter] = []
            sentence_index = 0
        
        en_match = re.search(r'english:\s*"([^"]+)"', line)
        if en_match and current_chapter is not None:
            sentence_index += 1
            chapters[current_chapter].append({
                'index': sentence_index,
                'text': en_match.group(1)
            })
    
    return chapters

async def generate_audio_azure(session, text, output_file):
    """使用 Azure Speech Service 生成单个音频文件"""
    ssml = f'''<speak version="1.0" xml:lang="en-US">
    <voice name="{VOICE_NAME}">
        <prosody rate="-5%">{text}</prosody>
    </voice>
</speak>'''
    
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": OUTPUT_FORMAT,
        "User-Agent": "NinjaKidTTS"
    }
    
    async with session.post(TTS_URL, headers=headers, data=ssml.encode('utf-8')) as resp:
        if resp.status == 200:
            audio_data = await resp.read()
            with open(output_file, 'wb') as f:
                f.write(audio_data)
            return True
        elif resp.status == 429:
            # 限速，等一等
            await asyncio.sleep(2)
            return False
        else:
            error_text = await resp.text()
            print(f"    Error {resp.status}: {error_text[:100]}")
            return False

async def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    js_file = os.path.join(script_dir, 'ninja_kid_data.js')
    audio_dir = os.path.join(script_dir, 'audio')
    
    chapters = extract_sentences_from_js(js_file)
    total = sum(len(sents) for sents in chapters.values())
    generated = 0
    
    print(f"Azure Speech Service TTS (声音: {VOICE_NAME})")
    print(f"共 {len(chapters)} 章，{total} 个句子需要生成音频\n")
    
    async with aiohttp.ClientSession() as session:
        for ch_num in sorted(chapters.keys()):
            sents = chapters[ch_num]
            ch_dir = os.path.join(audio_dir, f'ch{ch_num}')
            os.makedirs(ch_dir, exist_ok=True)
            
            print(f"第 {ch_num} 章: {len(sents)} 个句子")
            
            for sent in sents:
                output_file = os.path.join(ch_dir, f's{sent["index"]}.mp3')
                
                # 重试机制
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        success = await generate_audio_azure(session, sent['text'], output_file)
                        if success:
                            generated += 1
                            print(f"  [{generated}/{total}] ch{ch_num}/s{sent['index']}.mp3 ✓")
                            break
                        else:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(1)
                    except Exception as e:
                        print(f"  Attempt {attempt+1} error: {e}")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                
                # 避免限速（每秒约3-4个请求）
                await asyncio.sleep(0.3)
    
    print(f"\n完成! 已生成 {generated}/{total} 个音频文件")

if __name__ == '__main__':
    asyncio.run(main())
