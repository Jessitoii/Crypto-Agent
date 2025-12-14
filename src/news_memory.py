import sqlite3
import time
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import re

class NewsMemory:
    def __init__(self, db_path="news_history.db"):
        self.db_path = db_path
        self._init_db()
        self.vectorizer = TfidfVectorizer(stop_words='english')

    def _init_db(self):
        """Veritabanını ve tabloyu oluşturur."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT,
                content TEXT,
                timestamp REAL
            )
        ''')
        # Performans için index ekleyelim
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON news (timestamp)')
        conn.commit()
        conn.close()

    def clean_text(self, text):
        """Metni temizler (basit pre-processing)."""
        text = text.lower()
        text = re.sub(r'http\S+', '', text) # Linkleri sil
        text = re.sub(r'[^\w\s]', '', text) # Özel karakterleri sil
        return text

    def is_duplicate(self, new_text, threshold=0.75):
        """
        Gelen haberi son haberlerle karşılaştırır.
        Benzerlik oranı threshold'u geçerse True döner.
        """
        clean_new = self.clean_text(new_text)
        if not clean_new.strip(): return True, 1.0 # Boş metin duplicate sayılsın

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sadece son 24 saatteki veya son 100 haberi çek (Hız optimizasyonu)
        limit_time = time.time() - (24 * 60 * 60)
        cursor.execute('SELECT content FROM news WHERE timestamp > ? ORDER BY id DESC LIMIT 100', (limit_time,))
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return False, 0.0

        past_news = [self.clean_text(row[0]) for row in rows]
        
        # Vektörleştirme
        try:
            # Corpus: Geçmiş haberler + Yeni haber
            corpus = past_news + [clean_new]
            tfidf_matrix = self.vectorizer.fit_transform(corpus)
            
            # Son eleman (yeni haber) ile diğerlerinin benzerliğini hesapla
            # tfidf_matrix[-1] bizim yeni haberimiz
            similarities = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])
            
            # En yüksek benzerlik oranını bul
            max_sim = similarities.flatten().max() if similarities.size > 0 else 0.0
            
            if max_sim >= threshold:
                print(f"🛑 [BENZERLİK] Tespit edildi: {max_sim:.2f} (Reddedildi)")
                return True, max_sim
            
            return False, max_sim
            
        except Exception as e:
            print(f"⚠️ [MEMORY HATA] {e}")
            return False, 0.0

    def add_news(self, source, content):
        """Haberi veritabanına kaydeder."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO news (source, content, timestamp) VALUES (?, ?, ?)', 
                          (source, content, time.time()))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"❌ DB Yazma Hatası: {e}")