import pyaudio
import google.genai as genai
import json
from pydantic import BaseModel
from typing import List, Optional
import wave
import threading
import time
import os
import argparse
import shutil
from deepgram import DeepgramClient  # Only this!
import google.genai as genai  # pip install google-generativeai
from pydantic import BaseModel
from typing import List, Optional


# Pydantic models (define early for Gemini schema)
class Chapter(BaseModel):
    timestamp: str
    title: str
    key_points: List[str]

class ActionItem(BaseModel):
    task: str
    assignee: Optional[str] = None

class TranscriptSummary(BaseModel):
    summary: str
    chapters: List[Chapter]
    action_items: Optional[List[ActionItem]] = None

# Helper: format timestamp from Deepgram's ms str to [MM:SS]
def format_timestamp(ms_str):
    ms = int(float(ms_str))
    mins = ms // 60000
    secs = (ms % 60000) // 1000
    return f"{mins:02d}:{secs:02d}"

# 1. Recording function (with fixed channels)
def record_audio(filename, sample_rate=44100, channels=1, chunk=1024):
    p = pyaudio.PyAudio()
    stream = p.open(format=pyaudio.paInt16, channels=channels, rate=sample_rate,
                    input=True, frames_per_buffer=chunk)
    print("Press Enter to start recording...")
    input()
    print("Recording started. Press Enter again to stop...")
    frames = []
    recording = True

    def check_for_stop():
        nonlocal recording
        input()
        recording = False
        print("Recording stopped.")

    stop_thread = threading.Thread(target=check_for_stop)
    stop_thread.daemon = True
    stop_thread.start()

    while recording:
        data = stream.read(chunk)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
    wf.setframerate(sample_rate)
    wf.writeframes(b''.join(frames))
    wf.close()
    print(f"Audio saved to {filename}")




# 2. Transcribe with Deepgram

def transcribe_audio(audio_file):
    client = DeepgramClient(api_key="")

    with open(audio_file, "rb") as f:
        audio_data = f.read()

    response = client.listen.v1.media.transcribe_file(
        request=audio_data,  # No mimetype!
        model="nova-2",  # Try nova-2 (more reliable)
        smart_format=True,
        diarize=False,  # Disable temporarily
        language="en-US"
    )
    return response


# 3. Export formatted transcript

def format_timestamp(ms):
    """Convert Deepgram ms to MM:SS"""
    try:
        ms = float(ms)
        mins = int(ms // 60000)
        secs = int((ms % 60000) // 1000)
        return f"{mins:02d}:{secs:02d}"
    except:
        return "00:00"


def export_transcript(response, output_file):
    with open(output_file, "w", encoding='utf-8') as f:
        f.write("=== FULL TRANSCRIPT ===\n\n")

        results = response.results
        channels = results.channels
        alternative = channels[0].alternatives[0]

        # 1. MAIN TRANSCRIPT (300+ words!)
        f.write(alternative.transcript)
        f.write("\n\n")

        # 2. PARAGRAPHS WITH TIMESTAMPS (your audio has them!)
        if hasattr(alternative, 'paragraphs') and alternative.paragraphs:
            f.write("=== PARAGRAPHS ===\n\n")
            for para in alternative.paragraphs.paragraphs:
                start_time = format_timestamp(para.start)
                f.write(f"[{start_time}] ")
                for sentence in para.sentences:
                    f.write(sentence.text + " ")
                f.write("\n\n")

        # 3. WORDS WITH TIMESTAMPS
        f.write("=== WORDS ===\n")
        for word in alternative.words[:20]:  # First 20 words
            start = format_timestamp(word.start * 1000)
            f.write(f"[{start}] {word.punctuated_word} ")
        f.write("...\n")

        f.write("\n=== STATS ===\n")
        f.write(f"Words: {len(alternative.words)}\n")
        f.write(f"Duration: {response.metadata.duration:.1f}s\n")
        f.write(f"Confidence: {alternative.confidence:.3f}\n")

    print(f" FULL TRANSCRIPT SAVED: {output_file}")
    print(f" {len(alternative.words)} words detected!")


# 4. Read transcript for LLM
def read_transcript(file_path):
    with open(file_path, 'r') as file:
        return file.read()

# 5. Analyze with Gemini (fixed client/response parsing)

def analyze_transcript(transcript_path, model="gemini-2.5-flash"):  # ← Changed
    transcript = read_transcript(transcript_path)

    client = genai.Client(api_key="")

    prompt = f"""
Analyze this meeting transcript and return structured notes in JSON format:

TRANSCRIPT:
{transcript}

Return ONLY valid JSON:
{{"summary": "3-sentence summary", "chapters": [{{"timestamp": "MM:SS", "title": "Chapter", "key_points": ["bullet1"]}}], "action_items": [{{"task": "TODO"}}]}}
"""

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    # Parse JSON response
    content = response.text
    notes = json.loads(content)
    return notes

# 6. Write notes to MD

def write_transcript_notes_to_md(notes, filename):
    """Handle both dict and Pydantic objects"""
    with open(filename, 'w', encoding='utf-8') as file:
        file.write("# MEETING NOTES\n\n")

        # Handle dict (from json.loads)
        if isinstance(notes, dict):
            summary = notes.get('summary', 'No summary')
            chapters = notes.get('chapters', [])
            action_items = notes.get('action_items', [])
        else:  # Pydantic object
            summary = notes.summary
            chapters = notes.chapters
            action_items = notes.action_items or []

        file.write("## Summary\n")
        file.write(f"{summary}\n\n")

        file.write("## Chapters\n\n")
        for chapter in chapters:
            timestamp = chapter.get('timestamp', '00:00') if isinstance(chapter, dict) else chapter.timestamp
            title = chapter.get('title', 'Untitled') if isinstance(chapter, dict) else chapter.title
            key_points = chapter.get('key_points', []) if isinstance(chapter, dict) else chapter.key_points

            file.write(f"### [{timestamp}] {title}\n\n")
            for point in key_points:
                file.write(f"- {point}\n")
            file.write("\n")

        file.write("## Action Items\n\n")
        for item in action_items:
            task = item.get('task', 'No task') if isinstance(item, dict) else item.task
            assignee = f" - {item.get('assignee', '')}" if isinstance(item, dict) else f" - {item.assignee}"
            file.write(f"- {task}{assignee}\n")


# 7. Main CLI
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", type=str, help="Pre-recorded audio file")
    parser.add_argument("-d", "--dir", type=str, default="output", help="Output dir")
    parser.add_argument("-m", "--model", type=str, default="gemini-2.5-flash", help="LLM model")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    os.makedirs(args.dir, exist_ok=True)
    if args.file:
        audio_file = args.file
        dest = os.path.join(args.dir, os.path.basename(audio_file))
        #if audio_file != dest:
            #shutil.copy2(audio_file, dest)
          #  audio_file = dest
    else:
        audio_file = f"{args.dir}/audio_to_transcribe.wav"
        record_audio(audio_file)
    output_file = f"{args.dir}/transcript.txt"
    response = transcribe_audio(audio_file)
    print(f"Generating transcript: {output_file}")
    export_transcript(response, output_file)
    print("Analyzing...")
    notes = analyze_transcript(output_file, args.model)
    write_transcript_notes_to_md(notes, f"{args.dir}/transcript_notes.md")
    print("Done! Check output dir.")
