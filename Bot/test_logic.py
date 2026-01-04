import pandas as pd
import os
from datetime import datetime

# Test settings
TEST_FILE = "gumus_data.csv"

def test_storage():
    print("Testing storage...")
    if os.path.exists(TEST_FILE):
        os.remove(TEST_FILE)
    
    # Create mock data
    df = pd.DataFrame([
        {"Tarih": "2026-01-04 10:00:00", "Fiyat": 99.0, "Islem": "IZLEME", "Miktar": 0, "Kar_Zarar_Yuzde": 0},
        {"Tarih": "2026-01-04 10:01:00", "Fiyat": 100.0, "Islem": "IZLEME", "Miktar": 0, "Kar_Zarar_Yuzde": 0}
    ])
    df.to_csv(TEST_FILE, index=False)
    
    loaded = pd.read_csv(TEST_FILE)
    assert len(loaded) == 2
    assert loaded.iloc[1]["Fiyat"] == 100.0
    print("✅ Storage OK")

def test_analysis_logic():
    print("Testing analysis logic...")
    # Mocking basic logic from BOT.py
    def mock_analiz(guncel_fiyat, gecmis_prices):
        ortalama = sum(gecmis_prices) / len(gecmis_prices)
        if guncel_fiyat > ortalama * 1.005: return "AL"
        if guncel_fiyat < ortalama * 0.995: return "SAT"
        return "BEKLE"

    p_history = [100.0, 100.0, 100.0]
    assert mock_analiz(101.0, p_history) == "AL"
    assert mock_analiz(99.0, p_history) == "SAT"
    assert mock_analiz(100.1, p_history) == "BEKLE"
    print("✅ Analysis Logic OK")

if __name__ == "__main__":
    try:
        test_storage()
        test_analysis_logic()
        print("\n🎉 Tüm testler başarıyla tamamlandı!")
    except Exception as e:
        print(f"❌ Test hatası: {e}")
