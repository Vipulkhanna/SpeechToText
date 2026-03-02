Speech-to-Text Note-Taking App

This project is a speech-to-text note-taking application that records audio, transcribes it into structured text and generates intelligent summaries.

Core Components:

1. Audio Recording

The application captures audio input and stores it for processing. Audio recording is implemented using Python’s pyaudio and wave libraries, enabling on-demand recording and file storage.

2. Speech-to-Text (STT)

Once recorded, the audio is transcribed into a structured and timestamped transcript.

Transcription is powered by Deepgram’s enterprise-grade speech-to-text APIs. The resulting transcript includes timestamps and speaker labels (when applicable).

3. Intelligent Processing

After transcription, the application generates a concise, meeting-minutes-style document that highlights the most important information.

This includes:

High-level summaries

A table of contents with timestamps

Chapter segmentation

Key discussion points per section

Identified action items

A Large Language Model, Gemini in this case is used to generate structured summaries and extract meaningful insights from the transcript.

Additional Feature:

Exporting transcripts and summaries to Markdown files.

Tech Stack

Language: Python

Audio Recording: pyaudio, wave

Transcription: Deepgram Speech-to-Text API

Summarization & Structuring: Gemini LLM integration
