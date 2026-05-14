"""
SQLite DB 관리 모듈
병원 정보 (병원명, 교수명, 이메일, 계약례수 등) 저장/조회
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "newsletter.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    """DB 초기화 (최초 1회)"""
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS hospitals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT NOT NULL,
                professor TEXT NOT NULL,
                email TEXT,
                site_contracted INTEGER DEFAULT 0,
                site_enrolled INTEGER DEFAULT 0,
                site_ecrf INTEGER DEFAULT 0,
                site_delta INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS send_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hospital_name TEXT,
                professor TEXT,
                email TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT
            )
        """)
        conn.commit()

def upsert_hospital(hospital_name, professor, email="", site_contracted=0,
                     site_enrolled=0, site_ecrf=0, site_delta=0):
    """병원 정보 삽입 또는 업데이트"""
    with get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM hospitals WHERE hospital_name=? AND professor=?",
            (hospital_name, professor)
        ).fetchone()
        if existing:
            conn.execute("""
                UPDATE hospitals SET email=?, site_contracted=?, site_enrolled=?,
                site_ecrf=?, site_delta=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            """, (email, site_contracted, site_enrolled, site_ecrf, site_delta, existing[0]))
        else:
            conn.execute("""
                INSERT INTO hospitals (hospital_name, professor, email,
                site_contracted, site_enrolled, site_ecrf, site_delta)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (hospital_name, professor, email, site_contracted,
                  site_enrolled, site_ecrf, site_delta))
        conn.commit()

def get_all_hospitals():
    """전체 병원 목록 반환 (id 포함)"""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, hospital_name, professor, email, site_contracted, "
            "site_enrolled, site_ecrf, site_delta FROM hospitals ORDER BY hospital_name"
        ).fetchall()
    return [
        {
            "id": r[0], "hospital_name": r[1], "professor": r[2], "email": r[3],
            "site_contracted": r[4], "site_enrolled": r[5],
            "site_ecrf": r[6], "site_delta": r[7],
        }
        for r in rows
    ]

def update_hospital(id, hospital_name, professor, email, site_contracted,
                    site_enrolled, site_ecrf, site_delta):
    """병원 정보 수정"""
    with get_conn() as conn:
        conn.execute("""
            UPDATE hospitals SET hospital_name=?, professor=?, email=?,
            site_contracted=?, site_enrolled=?, site_ecrf=?, site_delta=?,
            updated_at=CURRENT_TIMESTAMP WHERE id=?
        """, (hospital_name, professor, email, site_contracted,
              site_enrolled, site_ecrf, site_delta, id))
        conn.commit()

def delete_hospital(id):
    """병원 정보 삭제"""
    with get_conn() as conn:
        conn.execute("DELETE FROM hospitals WHERE id=?", (id,))
        conn.commit()

def log_send(hospital_name, professor, email, status="sent"):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO send_log (hospital_name, professor, email, status) VALUES (?,?,?,?)",
            (hospital_name, professor, email, status)
        )
        conn.commit()

def get_send_log():
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT hospital_name, professor, email, sent_at, status FROM send_log ORDER BY sent_at DESC LIMIT 50"
        ).fetchall()
    return [{"hospital_name": r[0], "professor": r[1], "email": r[2], "sent_at": r[3], "status": r[4]} for r in rows]

# 앱 시작 시 자동 초기화
init_db()
