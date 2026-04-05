import re
import string
import mysql.connector
from google import genai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from dotenv import load_dotenv
import os

load_dotenv()


class CompanyChatbot:
    def __init__(self):
        self.connection = mysql.connector.connect(
            host=os.getenv("MYSQLHOST", "127.0.0.1"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT", "3306")),
            use_pure=True
        )

        self.cursor = self.connection.cursor(dictionary=True)
        self.stop_words = set(stopwords.words("english"))

        self.high_confidence = 0.6
        self.medium_confidence = 0.35

        # ✅ secure API key (no hardcoding)
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    def preprocess_text(self, text):
        text = text.lower()
        text = re.sub(f"[{re.escape(string.punctuation)}]", " ", text)
        tokens = word_tokenize(text)

        filtered = []
        for word in tokens:
            if word.isalnum() and word not in self.stop_words:
                filtered.append(word)

        return " ".join(filtered)

    def handle_intents(self, text):
        text = text.lower().strip()

        if text in ["hi", "hello", "hey", "hii"]:
            return "Hello! How can I help you today?"

        if "how are you" in text:
            return "I'm doing great! How can I assist you?"

        if "your name" in text or "who are you" in text:
            return "I’m your company support assistant. I’m here to help you with our services, projects, pricing, and support-related questions."

        if "what can you do" in text:
            return "I can help you with our company services, web and mobile application development, project details, pricing information, maintenance support, and contact guidance."

        if "services" in text and len(text.split()) <= 4:
            return "We provide web apps, mobile apps, software solutions, and maintenance services."

        if "contact" in text and len(text.split()) <= 4:
            return "You can contact our team via email or phone. Please check our contact page."

        if "price" in text or "cost" in text:
            return "Project cost depends on your requirements. Please contact us for a detailed quote."

        if "thanks" in text or "thank you" in text:
            return "You're welcome."

        if text in ["bye", "goodbye", "see you"]:
            return "Goodbye! Have a great day."

        return None

    def get_ai_response(self, user_question):
        try:
            prompt = f"""
You are the official support assistant for our software company website.

Rules:
- Speak like the lax 360 pvt limited company support assistant
- Never mention AI, Gemini, or backend
- Use simple English
- Keep answers short and clear
- Be friendly and professional

User question:
{user_question}
"""
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )

            if hasattr(response, "text") and response.text:
                return response.text.strip()

            return "I’m here to help you. Please rephrase your question."

        except Exception as e:
            print("AI ERROR:", str(e))
            return "Sorry, support assistant is temporarily unavailable. Please contact us."

    # ✅ UPDATED TABLE NAMES

    def get_all_faqs(self):
        self.cursor.execute("SELECT * FROM smart_faq")
        return self.cursor.fetchall()

    def get_exact_answer(self, user_question):
        query = "SELECT answer FROM smart_faq WHERE LOWER(question) = LOWER(%s)"
        self.cursor.execute(query, (user_question,))
        result = self.cursor.fetchone()
        return result["answer"] if result else None

    def save_unknown_question(self, question):
        check = "SELECT id FROM smart_unknown_questions WHERE LOWER(question)=LOWER(%s)"
        self.cursor.execute(check, (question,))
        if not self.cursor.fetchone():
            self.cursor.execute(
                "INSERT INTO smart_unknown_questions (question) VALUES (%s)",
                (question,)
            )
            self.connection.commit()

    def save_chat_history(self, q, a):
        self.cursor.execute(
            "INSERT INTO smart_chat_history (user_question, bot_answer) VALUES (%s, %s)",
            (q, a)
        )
        self.connection.commit()

    def get_response(self, user_question):
        user_question = user_question.strip()

        if not user_question:
            return "Please enter your question."

        intent_response = self.handle_intents(user_question)
        if intent_response:
            self.save_chat_history(user_question, intent_response)
            return intent_response

        exact_answer = self.get_exact_answer(user_question)
        if exact_answer:
            self.save_chat_history(user_question, exact_answer)
            return exact_answer

        faqs = self.get_all_faqs()

        if len(faqs) == 0:
            reply = "FAQ data not available."
            self.save_chat_history(user_question, reply)
            return reply

        questions = [f["question"] for f in faqs]
        answers = [f["answer"] for f in faqs]

        processed_qs = [self.preprocess_text(q) for q in questions]
        processed_input = self.preprocess_text(user_question)

        if processed_input == "":
            reply = "Please ask something related to our services."
            self.save_chat_history(user_question, reply)
            return reply

        vectorizer = TfidfVectorizer()
        tfidf = vectorizer.fit_transform(processed_qs + [processed_input])

        scores = cosine_similarity(tfidf[-1], tfidf[:-1])
        best_index = int(scores.argmax())
        best_score = float(scores[0][best_index])

        if best_score >= self.high_confidence:
            reply = answers[best_index]

        elif best_score >= self.medium_confidence:
            reply = "I think this might help you:\n\n" + answers[best_index]

        else:
            reply = self.get_ai_response(user_question)
            self.save_unknown_question(user_question)

        self.save_chat_history(user_question, reply)
        return reply

    def get_faq_data(self):
        self.cursor.execute("SELECT * FROM smart_faq ORDER BY id DESC")
        return self.cursor.fetchall()

    def get_unknown_questions(self):
        self.cursor.execute("SELECT * FROM smart_unknown_questions ORDER BY id DESC")
        return self.cursor.fetchall()

    def get_chat_history(self):
        self.cursor.execute("SELECT * FROM smart_chat_history ORDER BY id DESC")
        return self.cursor.fetchall()

    def add_faq(self, question, answer):
        self.cursor.execute(
            "INSERT INTO smart_faq (question, answer) VALUES (%s, %s)",
            (question, answer)
        )
        self.connection.commit()

    def delete_faq(self, faq_id):
        self.cursor.execute("DELETE FROM smart_faq WHERE id = %s", (faq_id,))
        self.connection.commit()

    def update_faq(self, faq_id, question, answer):
        self.cursor.execute(
            "UPDATE smart_faq SET question = %s, answer = %s WHERE id = %s",
            (question, answer, faq_id)
        )
        self.connection.commit()

    def get_unknown_question_by_id(self, question_id):
        self.cursor.execute(
            "SELECT * FROM smart_unknown_questions WHERE id = %s",
            (question_id,)
        )
        return self.cursor.fetchone()

    def convert_unknown_to_faq(self, question_id, answer):
        unknown = self.get_unknown_question_by_id(question_id)

        if unknown:
            self.cursor.execute(
                "INSERT INTO smart_faq (question, answer) VALUES (%s, %s)",
                (unknown["question"], answer)
            )

            self.cursor.execute(
                "DELETE FROM smart_unknown_questions WHERE id = %s",
                (question_id,)
            )

            self.connection.commit()

    def close(self):
        self.cursor.close()
        self.connection.close()