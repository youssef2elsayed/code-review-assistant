# Explainable Code Review Assistant

This project is a web-based code review tool designed to help beginner programmers understand and improve their code.

The system supports Python, C++ and JavaScript and provides structured feedback explaining:
- what the issue is
- why it matters
- how to fix it

## Features

- Multi-language support (Python, C++, JavaScript)
- AI-based code analysis using OpenAI API
- Beginner-friendly explanations
- Code complexity scoring
- Interactive interface with issue highlighting

## Technologies Used

- Python (Flask)
- HTML, CSS, Bootstrap
- OpenAI API

## How to Run

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask openai
export OPENAI_API_KEY=your_api_key_here
python app.py
