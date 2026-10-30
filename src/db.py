import sqlite3
import random
from datetime import datetime

DB_NAME = "betovertwo.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Tabela de Jogos
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jogos (
            id TEXT PRIMARY KEY,
            equipas TEXT,
            data_hora_str TEXT,
            data_hora_obj TEXT,
            odd TEXT,
            status TEXT DEFAULT 'Pendente'
        )
    ''')
    
    # Tabela de Cliques / Participantes
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cliques (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogo_id TEXT,
            user_id INTEGER,
            user_name TEXT,
            ref_codigo TEXT,
            estado_pagamento TEXT DEFAULT 'Pendente',
            UNIQUE(jogo_id, user_id)
        )
    ''')
    
    conn.commit()
    conn.close()

def reset_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS cliques")
    cursor.execute("DROP TABLE IF EXISTS jogos")
    conn.commit()
    conn.close()
    init_db()

def apagar_jogo_por_id(jogo_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM jogos WHERE id = ?", (jogo_id,))
    if not cursor.fetchone():
        conn.close()
        return False
    cursor.execute("DELETE FROM cliques WHERE jogo_id = ?", (jogo_id,))
    cursor.execute("DELETE FROM jogos WHERE id = ?", (jogo_id,))
    conn.commit()
    conn.close()
    return True

def guardar_jogo(equipas, data_hora_str, data_hora_obj, odd):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM jogos")
    jogos_existentes = cursor.fetchall()
    novo_id_num = len(jogos_existentes) + 1
    jogo_id = f"J{novo_id_num}"
    
    cursor.execute('''
        INSERT INTO jogos (id, equipas, data_hora_str, data_hora_obj, odd, status)
        VALUES (?, ?, ?, ?, ?, 'Pendente')
    ''', (jogo_id, equipas, data_hora_str, data_hora_obj.strftime("%Y-%m-%d %H:%M:%S"), odd))
    
    conn.commit()
    conn.close()
    return jogo_id

def obter_jogo(jogo_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, equipas, data_hora_str, data_hora_obj, odd, status FROM jogos WHERE id = ?", (jogo_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "equipas": row[1],
            "data_hora_str": row[2],
            "data_hora_obj": row[3],
            "odd": row[4],
            "status": row[5]
        }
    return None

def obter_todos_os_jogos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, equipas, odd, status FROM jogos")
    rows = cursor.fetchall()
    conn.close()
    
    jogos = []
    for r in rows:
        jogos.append({
            "id": r[0],
            "equipas": r[1],
            "odd": r[2],
            "status": r[3]
        })
    return jogos

def registar_clique(jogo_id, user_id, user_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT ref_codigo FROM cliques WHERE jogo_id = ? AND user_id = ?", (jogo_id, user_id))
    row = cursor.fetchone()
    
    if row:
        conn.close()
        return row[0]
        
    ref_codigo = f"{jogo_id}-{random.randint(1000, 9999)}"
    
    cursor.execute('''
        INSERT OR IGNORE INTO cliques (jogo_id, user_id, user_name, ref_codigo, estado_pagamento)
        VALUES (?, ?, ?, ?, 'Pendente')
    ''', (jogo_id, user_id, user_name, ref_codigo))
    
    conn.commit()
    conn.close()
    return ref_codigo

def processar_resultado_jogo(jogo_id, status_final):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, equipas, odd FROM jogos WHERE id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    if not jogo:
        conn.close()
        return None
        
    cursor.execute("UPDATE jogos SET status = ? WHERE id = ?", (status_final, jogo_id))
    
    cobrancas = []
    if status_final == "Green":
        cursor.execute("SELECT user_id, ref_codigo FROM cliques WHERE jogo_id = ?", (jogo_id,))
        cobrancas = cursor.fetchall()
        
    conn.commit()
    conn.close()
    
    return {
        "equipas": jogo[1],
        "odd": jogo[2],
        "cobrancas": cobrancas
    }

def obter_dados_lista(jogo_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, equipas, odd, status FROM jogos WHERE id = ?", (jogo_id,))
    jogo_row = cursor.fetchone()
    if not jogo_row:
        conn.close()
        return None
        
    jogo = {
        "id": jogo_row[0],
        "equipas": jogo_row[1],
        "odd": jogo_row[2],
        "status": jogo_row[3]
    }
    
    cursor.execute("SELECT user_id, user_name, ref_codigo, estado_pagamento FROM cliques WHERE jogo_id = ?", (jogo_id,))
    participantes_rows = cursor.fetchall()
    conn.close()
    
    participantes = []
    for p in participantes_rows:
        participantes.append({
            "user_id": p[0],
            "user_name": p[1],
            "ref_codigo": p[2],
            "estado_pagamento": p[3]
        })
        
    return jogo, participantes

def confirmar_pagamento_por_ref(ref_codigo):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT jogo_id, user_id, user_name, estado_pagamento FROM cliques WHERE ref_codigo = ?", (ref_codigo,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return None
        
    jogo_id, user_id, user_name, estado_atual = row
    
    if estado_atual == "Pago":
        conn.close()
        return {"status": "ja_pago", "user_name": user_name}
        
    cursor.execute("UPDATE cliques SET estado_pagamento = 'Pago' WHERE ref_codigo = ?", (ref_codigo,))
    conn.commit()
    conn.close()
    
    return {
        "status": "sucesso",
        "jogo_id": jogo_id,
        "user_id": user_id,
        "user_name": user_name
    }

def obter_estatisticas_globais():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM jogos WHERE status IN ('Green', 'Red')")
    publicados = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jogos WHERE status = 'Green'")
    greens = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM jogos WHERE status = 'Red'")
    reds = cursor.fetchone()[0]
    
    conn.close()
    return publicados, greens, reds
