import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime
import pandas as pd
import re
import os
import msvcrt

# ---- Ayarlar ve Dosya Yolları ----
DATA_FILE = "gumus_data.csv"

# ---- Global Session Ayarları (Bağlantı hatalarını önlemek için) ----
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
})

# ---- Yardımcı Fonksiyon: Kesintisiz Bekleme ve Tuş Dinleme ----
def bekle_ve_komut_dinle(saniye=60):
    """
    Belirtilen süre boyunca beklerken klavyeyi dinler.
    'a' -> Alış, 's' -> Satış, 'q' -> Çıkış
    """
    print(f"\n[KLAVYE]: 'a' (Al), 's' (Sat), 'q' (Çıkış) tuşlarını kullanabilirsiniz.")
    end_time = time.time() + saniye
    while time.time() < end_time:
        if msvcrt.kbhit():
            tus = msvcrt.getch().decode('utf-8').lower()
            if tus == 'a': return "AL"
            if tus == 's': return "SAT"
            if tus == 'q': return "CIKIS"
        time.sleep(0.1)
    return None

# ---- Veri Kaydetme/Yükleme Fonksiyonları ----
def verileri_yukle():
    """
    CSV dosyasından geçmiş verileri yükler ve mevcut portföyü hesaplar.
    :return: (df, toplam_gram, ortalama_maliyet)
    """
    cols = ["Tarih", "Fiyat", "Islem", "Miktar", "Kar_Zarar_Yuzde"]
    if os.path.exists(DATA_FILE):
        try:
            df = pd.read_csv(DATA_FILE)
            
            # Portföy Hesaplama
            toplam_gram = 0.0
            toplam_maliyet = 0.0
            
            for _, row in df.iterrows():
                row_miktar = float(row['Miktar'])
                row_fiyat = float(row['Fiyat'])
                
                if row['Islem'] == "ALIS":
                    toplam_gram += row_miktar
                    toplam_maliyet += (row_fiyat * row_miktar)
                elif row['Islem'] == "SATIS":
                    # Basit mantık: Satış tüm varlığı sıfırlar (veya miktarı kadar azaltır)
                    # Kullanıcı tümünü satıyor varsayıyoruz
                    toplam_gram = 0.0
                    toplam_maliyet = 0.0
            
            ortalama_maliyet = toplam_maliyet / toplam_gram if toplam_gram > 0 else 0.0
            return df, toplam_gram, ortalama_maliyet
            
        except Exception as e:
            print(f"⚠️ Veri dosyası okunamadı veya bozuk. Hata: {e}")
            return pd.DataFrame(columns=cols), 0.0, 0.0
    else:
        return pd.DataFrame(columns=cols), 0.0, 0.0

def veri_kaydet(df):
    """Verileri CSV dosyasına kaydeder."""
    try:
        df.to_csv(DATA_FILE, index=False)
    except Exception as e:
        print(f"⚠️ Veri kaydedilemedi: {e}")

# ---- Türk Piyasasından Veri Çekme Fonksiyonu (BigPara) ----
def gumus_fiyati_bigpara():
    """
    BigPara'dan Türkiye'nin güncel gümüş fiyatını veri olarak çeker.
    Hatalara karşı 3 kez deneme yapar.
    """
    url = "https://bigpara.hurriyet.com.tr/altin/"
    deneme_sayisi = 3

    for i in range(deneme_sayisi):
        try:
            response = session.get(url, timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                
                # "Gümüş (TL/GR)" metnini içeren <b> tag'ini bul
                silver_label = soup.find("b", string=re.compile(r"Gümüş \(TL/GR\)"))
                
                if silver_label:
                    silver_row = silver_label.find_parent("ul")
                    if silver_row:
                        cells = silver_row.find_all("li")
                        if len(cells) >= 3:
                            # Satış fiyatını al (3. hücre)
                            fiyat_str = cells[2].text.strip().replace(".", "").replace(",", ".")
                            return float(fiyat_str)
            else:
                print(f"⚠️ BigPara yanıt vermedi (Kod: {response.status_code}). Tekrar deneniyor... ({i+1}/{deneme_sayisi})")
        
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            print(f"🔄 Bağlantı hatası/Zaman aşımı ({e}). Tekrar deneniyor... ({i+1}/{deneme_sayisi})")
            time.sleep(2) # Hatalı durumda 2 saniye bekle
        except Exception as e:
            print(f"⚠️ Beklenmedik bir hata oluştu: {e}")
            break
            
    print("❌ Gümüş fiyatı tüm denemelere rağmen alınamadı.")
    return None

# ---- Analiz ve Sinyal Fonksiyonu ----
def analiz_et(guncel_fiyat, gecmis_df):
    """Geçmiş verilere bakarak basit bir trend analizi yapar."""
    if len(gecmis_df) < 2:
        return "Yetersiz Veri", "⚪ BEKLE"
    
    # Son 10 kaydın ortalaması
    son_kayitlar = gecmis_df.tail(10)["Fiyat"].astype(float)
    ortalama = son_kayitlar.mean()
    
    if guncel_fiyat > ortalama * 1.005: # Ortalamanın %0.5 üstündeyse
        return "Yükseliş Trendi", "🟢 AL (Trend Yukarı)"
    elif guncel_fiyat < ortalama * 0.995: # Ortalamanın %0.5 altındaysa
        return "Düşüş Trendi", "🔴 SAT (Trend Aşağı)"
    else:
        return "Yatay Seyir", "🟡 BEKLE (Stabil)"

# ---- Kâr/Zarar Hesaplama Fonksiyonu ----
def kar_zarar_detayli(alis_fiyati, miktar, guncel_fiyat):
    """Kâr/zarar durumunu tutar ve yüzde olarak hesaplar."""
    if alis_fiyati == 0: return 0, 0
    toplam_maliyet = alis_fiyati * miktar
    guncel_deger = guncel_fiyat * miktar
    kazanc = guncel_deger - toplam_maliyet
    yuzde = (kazanc / toplam_maliyet) * 100
    return kazanc, yuzde

# ---- Sürekli Çalışan Bot ----
def gumus_bot_surekli():
    print("\n" + "="*50)
    print("🚀 GÜMÜŞ TAKİP, ANALİZ VE PORTFÖY BOTU")
    print("Sistem: Kesintisiz İzleme & Kümülatif Varlık")
    print("="*50 + "\n")

    fiyat_gecmisi_df, toplam_gram, ortalama_maliyet = verileri_yukle()
    
    if toplam_gram > 0:
        print(f"📦 Mevcut Varlık: {toplam_gram:.2f} Gram")
        print(f"💰 Ort. Maliyet: {ortalama_maliyet:.2f} TL")
        print("-" * 30)

    try:
        # Başlangıçta Alış Sor (Sadece 1 kez, blocking)
        if toplam_gram == 0:
            secim = input("👉 Başlangıç alımı yapmak ister misiniz? (e/h): ").lower()
            if secim == 'e':
                try:
                    guncel = gumus_fiyati_bigpara()
                    if guncel:
                        print(f"Anlık Fiyat: {guncel:.2f} TL")
                        miktar = float(input("Kaç gram alacaksınız? "))
                        if miktar > 0:
                            tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            alis_kaydi = {"Tarih": tarih, "Fiyat": guncel, "Islem": "ALIS", "Miktar": miktar, "Kar_Zarar_Yuzde": 0}
                            fiyat_gecmisi_df = pd.concat([fiyat_gecmisi_df, pd.DataFrame([alis_kaydi])], ignore_index=True)
                            veri_kaydet(fiyat_gecmisi_df)
                            fiyat_gecmisi_df, toplam_gram, ortalama_maliyet = verileri_yukle()
                            print(f"✅ {miktar} gr alındı. İzleme başlıyor...")
                except ValueError: print("❌ Geçersiz miktar, izlemeye devam ediliyor...")

        while True:
            guncel_fiyat = gumus_fiyati_bigpara()
            if guncel_fiyat is None:
                time.sleep(30)
                continue

            tarih = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            trend, sinyal = analiz_et(guncel_fiyat, fiyat_gecmisi_df)

            # --- Dashboard ---
            print(f"\n[{tarih}] Fiyat: {guncel_fiyat:.2f} TL | Trend: {trend}")
            print(f"💡 Tavsiye: {sinyal}")
            
            if toplam_gram > 0:
                kazanc, yuzde = kar_zarar_detayli(ortalama_maliyet, toplam_gram, guncel_fiyat)
                renk = "🟢" if kazanc >= 0 else "🔴"
                print(f"📦 Portföy: {toplam_gram:.2f} Gr | Maliyet: {ortalama_maliyet:.2f} TL")
                print(f"📈 Durum  : {renk} {kazanc:.2f} TL ({yuzde:.2f}%)")
                
                if yuzde >= 2.0 or "🔴 SAT" in sinyal:
                    print("🔔 [DİKKAT]: Satış uyarısı var! 's' tuşuna basarak satabilirsiniz.")
            else:
                print("⚪ Henüz bir varlığınız bulunmuyor.")

            # Veriyi Kaydet (Log)
            yeni_veri = {"Tarih": tarih, "Fiyat": guncel_fiyat, "Islem": "IZLEME", "Miktar": 0, "Kar_Zarar_Yuzde": 0}
            fiyat_gecmisi_df = pd.concat([fiyat_gecmisi_df, pd.DataFrame([yeni_veri])], ignore_index=True)
            veri_kaydet(fiyat_gecmisi_df)

            # --- Komut Bekleme (Asla Durmaz, Tuş Bekler) ---
            komut = bekle_ve_komut_dinle(60)

            if komut == "AL":
                try:
                    miktar_ek = float(input(f"\n👉 Eklenecek miktar (Mevcut: {toplam_gram:.2f} gr): "))
                    if miktar_ek > 0:
                        tarih_islem = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        alis_kaydi = {"Tarih": tarih_islem, "Fiyat": guncel_fiyat, "Islem": "ALIS", "Miktar": miktar_ek, "Kar_Zarar_Yuzde": 0}
                        fiyat_gecmisi_df = pd.concat([fiyat_gecmisi_df, pd.DataFrame([alis_kaydi])], ignore_index=True)
                        veri_kaydet(fiyat_gecmisi_df)
                        # Portföyü yeniden yükle
                        fiyat_gecmisi_df, toplam_gram, ortalama_maliyet = verileri_yukle()
                        print(f"✅ Varlığınız {toplam_gram:.2f} gr'a yükseltildi.")
                except ValueError: print("❌ Hata: Geçerli bir sayı girilmedi.")
            
            elif komut == "SAT" and toplam_gram > 0:
                kazanc, yuzde = kar_zarar_detayli(ortalama_maliyet, toplam_gram, guncel_fiyat)
                print(f"\n📉 [SATIŞ]: {toplam_gram:.2f} gr satılacak. Kâr/Zarar: {kazanc:.2f} TL")
                if input("Onaylıyor musunuz? (e/h): ").lower() == 'e':
                    tarih_islem = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    satis_kaydi = {"Tarih": tarih_islem, "Fiyat": guncel_fiyat, "Islem": "SATIS", "Miktar": toplam_gram, "Kar_Zarar_Yuzde": yuzde}
                    fiyat_gecmisi_df = pd.concat([fiyat_gecmisi_df, pd.DataFrame([satis_kaydi])], ignore_index=True)
                    veri_kaydet(fiyat_gecmisi_df)
                    fiyat_gecmisi_df, toplam_gram, ortalama_maliyet = verileri_yukle()
                    print(f"✅ Tüm varlık satıldı.")
            
            elif komut == "CIKIS":
                print("\n👋 Bot kapatılıyor.")
                break
            
            print("-" * 40)

    except KeyboardInterrupt:
        print("\n👋 Bot durduruluyor. Tüm veriler kaydedildi.")

if __name__ == "__main__":
    gumus_bot_surekli()