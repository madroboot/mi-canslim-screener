import yfinance as yf
import pandas as pd
import numpy as np
import time
import json
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
MODO_PRUEBA = False # Si es True, solo escanea 20 para verificar
ARCHIVO_SALIDA = "data.json"

def obtener_lista_completa():
    """
    Para obtener 6000 acciones gratis, descargamos los componentes 
    del Russell 3000 o combinamos índices.
    """
    print("Obteniendo lista de tickers...")
    try:
        # Intentamos obtener S&P 500 + NASDAQ 100 como base sólida
        sp500 = pd.read_html('https://en.wikipedia.org/wiki/List_of_S%26P_500_companies')[0]['Symbol'].tolist()
        nasdaq = pd.read_html('https://en.wikipedia.org/wiki/Nasdaq-100#Components')[0]['Ticker'].tolist()
        tickers = list(set(sp500 + nasdaq))
        tickers = [t.replace('.', '-') for t in tickers]
        return tickers
    except:
        return ["NVDA", "AAPL", "MSFT", "TSLA", "FTAI", "APP", "ANF"]

def obtener_datos_lote(tickers):
    """Descarga datos de precios en masa para ganar velocidad."""
    try:
        data = yf.download(tickers, period="2y", interval="1d", group_by='ticker', progress=False, auto_adjust=True)
        return data
    except:
        return None

def analizar_accion(ticker, df_accion, sp500_close):
    try:
        if df_accion.empty or len(df_accion) < 200: return None
        
        close = df_accion['Close'].squeeze()
        high = df_accion['High'].squeeze()
        low = df_accion['Low'].squeeze()
        volume = df_accion['Volume'].squeeze()

        precio_actual = close.iloc[-1]
        
        # Técnicos
        sma50 = close.rolling(50).mean().iloc[-1]
        sma150 = close.rolling(150).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1]
        sma200_serie = close.rolling(200).mean()
        high_52 = high.rolling(252).max().iloc[-1]
        low_52 = low.rolling(252).min().iloc[-1]
        vol_promedio = volume.rolling(50).mean().iloc[-1]

        # RS Score simplificado
        roc_3m = close.pct_change(63).iloc[-1]
        fuerza_tecnica = roc_3m # Simplificado para velocidad

        # Puntuación N-Value
        score = 0
        if sma50 > sma150: score += 2**12
        if sma150 > sma200: score += 2**11
        if (0.75 * high_52) > (1.25 * low_52): score += 2**10
        if fuerza_tecnica > 0.1: score += 2**9
        if (precio_actual * vol_promedio) >= 20000000: score += 2**8
        if precio_actual > (0.75 * high_52): score += 2**7
        if precio_actual > 10: score += 2**6
        # Pendiente SMA200
        if len(sma200_serie) > 21 and sma200_serie.iloc[-1] > sma200_serie.iloc[-21]: score += 2**5
        if precio_actual > sma50: score += 2**3

        return {
            "t": ticker,
            "s": int(score),
            "p": round(float(precio_actual), 2),
            "rs": round(float(fuerza_tecnica * 100), 1)
        }
    except:
        return None

if __name__ == "__main__":
    tickers = obtener_lista_completa()
    if MODO_PRUEBA: tickers = tickers[:20]
    
    # 1. Obtener datos de mercado
    mkt = yf.download("^GSPC", period="2y", progress=False, auto_adjust=True)
    mkt_close = mkt['Close'].squeeze()
    
    resultados = []
    
    # 2. Procesar por lotes de 50 para no saturar la memoria
    lote_size = 50
    print(f"Escaneando {len(tickers)} acciones en lotes de {lote_size}...")
    
    for i in range(0, len(tickers), lote_size):
        lote_tickers = tickers[i:i+lote_size]
        data_lote = obtener_datos_lote(lote_tickers)
        
        if data_lote is None: continue
        
        for t in lote_tickers:
            try:
                # Extraer df de la accion del panel descargado
                if len(lote_tickers) > 1:
                    df_t = data_lote[t]
                else:
                    df_t = data_lote
                
                res = analizar_accion(t, df_t, mkt_close)
                if res: resultados.append(res)
            except:
                continue
        
        print(f"Progreso: {min(i+lote_size, len(tickers))}/{len(tickers)}", end="\r")
        time.sleep(1) # Respeto a la API

    # 3. Guardar JSON para la web
    salida = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "data": resultados
    }
    
    with open(ARCHIVO_SALIDA, "w") as f:
        json.dump(salida, f)
    
    print(f"\nProceso finalizado. {len(resultados)} acciones guardadas en {ARCHIVO_SALIDA}")