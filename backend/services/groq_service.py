import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()


def get_groq_reply(prompt: str) -> str:
    api_key = os.getenv('GROQ_API_KEY')
    model_name = os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile')

    if not api_key:
        raise RuntimeError('GROQ_API_KEY is missing from the environment.')

    client = Groq(api_key=api_key)
    chat_completion = client.chat.completions.create(
        messages=[
            {
                'role': 'user',
                'content': prompt,
            }
        ],
        model=model_name,
        temperature=0.7,
        max_tokens=400,
    )
    return chat_completion.choices[0].message.content.strip()
