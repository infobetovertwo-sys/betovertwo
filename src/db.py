import sqlite3
from datetime import datetime, timedelta
import random

DB_NAME = "betovertwo.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Permite aceder às colunas pelo nome (ex: row['equipas'])
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Tabela de Jogos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jogos (
            jogo_id TEXT PRIMARY KEY,
            equipas TEXT,
            data_hora_str TEXT,
            data_hora_obj TIMESTAMP,
            odd TEXT,
            status TEXT DEFAULT 'Pendente'
        )
    """)
    
    # Tabela de Cliques / Participantes por Jogo
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS participantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            jogo_id TEXT,
            user_id INTEGER,
            user_name TEXT,
            ref_codigo TEXT,
            estado_pagamento TEXT DEFAULT 'Pendente',
            data_limite TIMESTAMP,
            FOREIGN KEY (jogo_id) REFERENCES jogos (jogo_id)
        )
    """)
    
    # Tabela de Estatísticas Globais
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estatisticas (
            chave TEXT PRIMARY KEY,
            valor INTEGER
        )
    """)
    
    # Inicializar contadores se não existirem
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('publicados', 0)")
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('greens', 0)")
    cursor.execute("INSERT OR IGNORE INTO estatisticas (chave, valor) VALUES ('reds', 0)")
    
    conn.commit()
    conn.close()

def guardar_jogo(jogo_id, equipas, data_hora_str, data_hora_obj, odd):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO jogos (jogo_id, equipas, data_hora_str, data_hora_obj, odd, status)
        VALUES (?, ?, ?, ?, ?, 'Pendente')
    """, (jogo_id, equipas, data_hora_str, data_hora_obj, odd))
    
    cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'publicados'")
    conn.commit()
    conn.close()

def obter_jogo(jogo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    conn.close()
    return jogo

def registar_clique(jogo_id, user_id, user_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM participantes WHERE jogo_id = ? AND user_id = ?", (jogo_id, user_id))
    ja_registado = cursor.fetchone()
    
    if not ja_registado:
        cursor.execute("""
            INSERT INTO participantes (jogo_id, user_id, user_name, ref_codigo, estado_pagamento)
            VALUES (?, ?, ?, '', 'Aguardando Resultado')
        """, (jogo_id, user_id, user_name))
        conn.commit()
        registado_agora = True
    else:
        registado_agora = False
        
    conn.close()
    return registado_agora

def processar_resultado_jogo(jogo_id, res):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT equipas, odd FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    if not jogo:
        conn.close()
        return None
        
    cursor.execute("UPDATE jogos SET status = ? WHERE jogo_id = ?", (res, jogo_id))
    
    if res == "Green":
        cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'greens'")
        # Gerar referências e prazos de 24h para os participantes
        cursor.execute("SELECT user_id, user_name FROM participantes WHERE jogo_id = ?", (jogo_id,))
        participantes = cursor.fetchall()
        
        data_limite = datetime.now() + timedelta(hours=24)
        cobrancas = []
        
        for p in participantes:
            u_id, u_name = p
            ref_codigo = f"{jogo_id}-{random.randint(1000, 9999)}"
            
            cursor.execute("""
                UPDATE participantes 
                SET ref_codigo = ?, estado_pagamento = 'Pendente', data_limite = ? 
                WHERE jogo_id = ? AND user_id = ?
            """, (ref_codigo, data_limite, jogo_id, u_id))
            
            cobrancas.append((u_id, ref_codigo))
            
        conn.commit()
        conn.close()
        return {"equipas": jogo["equipas"], "odd": jogo["odd"], "cobrancas": cobrancas}
    else:
        cursor.execute("UPDATE estatisticas SET valor = valor + 1 WHERE chave = 'reds'")
        conn.commit()
        conn.close()
        return {"equipas": jogo["equipas"], "odd": jogo["odd"], "cobrancas": []}

def obter_dados_lista(jogo_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jogos WHERE jogo_id = ?", (jogo_id,))
    jogo = cursor.fetchone()
    
    if not jogo:
        conn.close()
        return None
        
    cursor.execute("SELECT ref_codigo, user_name, user_id, estado_pagamento FROM participantes WHERE jogo_id = ?", (jogo_id,))
    participantes = cursor.fetchall()
    conn.close()
    
    return jogo, participantes

def confirmar_pagamento_por_ref(ref):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, user_name, jogo_id, estado_pagamento FROM participantes WHERE ref_codigo = ?", (ref,))
    reg = cursor.fetchone()
    
    if not reg:
        conn.close()
        return None
        
    if reg["estado_pagamento"] == 'Pago':
        conn.close()
        return {"status": "ja_pago"}
        
    cursor.execute("UPDATE participantes SET estado_pagamento = 'Pago' WHERE ref_codigo = ?", (ref,))
    conn.commit()
    conn.close()
    
    return {
        "status": "sucesso",
        "user_id": reg["user_id"],
        "user_name": reg["user_name"],
        "jogo_id": reg["jogo_id"]
    }

def obter_estatisticas_globais():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'publicados'")
    pub = cursor.fetchone()["valor"]
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'greens'")
    greens = cursor.fetchone()["valor"]
    
    cursor.execute("SELECT valor FROM estatisticas WHERE chave = 'reds'")
    reds = cursor.fetchone()["valor"]
    
    conn.close()
    return pub, greens, reds
