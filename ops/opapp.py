import json
import os

import openai
import requests
from bs4 import BeautifulSoup
from flask import session
from langchain.chains import RetrievalQA
from langchain.chat_models import ChatOpenAI
from langchain.docstore.document import Document
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import Chroma


from config import Config


class LanguageModel:
    def __init__(self, aiKey=None):
        openai.api_key = aiKey if aiKey else os.getenv("OPENAI_API_KEY")
        if not openai.api_key:
            raise ValueError("OPENAI_API_KEY is not set in the environment")
        self.qa = None

    def doc_feed(self, txt, aiKey=None):
        key = aiKey if aiKey else os.getenv("OPENAI_API_KEY")
        embeddings = OpenAIEmbeddings(openai_api_key=key)
        doc = Document(page_content=txt)
        docsearch = Chroma.from_documents([doc], embeddings)
        # llm = InferenceOpenAI(model_name="gpt-3.5-turbo", temperature=0.2)
        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.2)
        self.qa = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=docsearch.as_retriever())

    def doc_query(self, question):
        if self.qa:
            ans = self.qa.run(question)
        else:
            ans = "Not yet."
        return ans

    def query_with_prompt_file(self, prompt_file_path, count, difficulties=()):
        with open(prompt_file_path, 'r') as prompt_file:
            prompt_data = json.load(prompt_file)
            quiz_prompt = prompt_data.get("quiz_prompt", "")
            quiz_prompt = quiz_prompt.format(count, difficulties[0], difficulties[1], difficulties[2])
        response = self.doc_query(quiz_prompt)
        return response

    def train_llm(self, txt, aiKey=None):
        self.doc_feed(txt=txt, aiKey=aiKey)


    def save_quiz_as_json(self, quiz_json, file_path):
        with open(file_path, 'w') as quiz_file:
            json.dump(quiz_json, quiz_file, indent=4)

    def save_response_as_json(self, response, file_path):
        with open(file_path, 'w') as response_file:
            json.dump(response, response_file, indent=4)

    def parse_quiz_response(self, response):
        quiz_lines = response.strip().split('\n')
        quiz_dict = {
            'title': quiz_lines[0].strip().split(': ')[1],
            'questions': []
        }

        for i in range(1, len(quiz_lines)):
            if not ('question' in quiz_lines[i].lower() and len(quiz_lines[i].strip().split(':'))>1):
                continue
            question_number = quiz_lines[i].strip().split(': ')[0]
            question_text = quiz_lines[i].strip().split(': ')[1]
            answer_options = [x.strip() for x in [quiz_lines[i + 1],quiz_lines[i + 2],quiz_lines[i + 3],quiz_lines[i + 4]]]
            correct_answer = quiz_lines[i + 5]
            i+=5
            if question_number:
                question_dict = {
                    'number': question_number,
                    'text': question_text,
                    'options': answer_options,
                    'correct_answer': correct_answer
                }

                quiz_dict['questions'].append(question_dict)

        return quiz_dict

class Util():

    def clean_article(self, article_text):
        cleaned_text = ' '.join(article_text.split())
        return cleaned_text

    def extract_text(self, links):
        corpus_text = ''
        key = session.sid
        session[key] = {} if not key in session else session[key]
        for l in links:
            if l not in session:
                article_text = self.save_link_content(l)
            article_text = session[l]
            corpus_text += f'{article_text}\n---\n'
        session[key]['corpus'] = corpus_text
        return corpus_text

    def save_link_content(self, link):
        try:
            response = requests.get(link)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            article = soup.find('article')
            if article:
                article_text = self.clean_article(article.get_text())
                # session_key = hashlib.md5(link.encode()).hexdigest()
                session[link] = article_text
                return article_text
        except Exception as e:
            return f"Error processing {link}: {str(e.args[1])}"

    def generate_quiz(self, key, links, difficulties):
        count = 0 if (session.sid not in session) or ('count' not in session[session.sid]) else session[session.sid]['count']
        if count < Config.quiz_limit:
            try:
                txt = self.get_text_corpus(links)
                lm = LanguageModel()
                if txt:
                    lm.train_llm(txt, key)
                else:
                    raise Exception("No text detected")
            except Exception as e:
                session[session.sid]['quiz'] = 'LLM training not done.'
                raise e

            try:
                counts = sum(difficulties)
                response = lm.query_with_prompt_file("./assets/quiztemplate.json", counts, difficulties)
                quiz_json = lm.parse_quiz_response(response)
                session[session.sid]['quiz'] = quiz_json
                if 'count' not in session[session.sid]:
                    session[session.sid]['count'] = 0
                session[session.sid]['count'] += 1
                return quiz_json
            except Exception as e:
                session[session.sid]['quiz'] = f'Quiz not generated: {e}'
                raise e
        else:
            session[session.sid]['quiz'] = f'Quiz generation limit reached : {Config.quiz_limit}'
            return f'Quiz generation limit reached : {Config.quiz_limit}'

    def get_text_corpus(self, links):
        corpus = session[session.sid]['corpus'] if session.sid in session and session[session.sid] and 'corpus' in session[session.sid] else self.extract_text(links)
        return corpus