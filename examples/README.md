# Örnek: MCP Videosu Üretim Akışı

22 dakikalık ham kayıttan 7 dakikalık yayına hazır YouTube videosu — gerçek bir akış.

## Kaynak

- **Format:** Selma'nın YouTube videosu, "Claude Code'da MCP Kullanımı" (Nisan 2026)
- **Ham kayıt:** ~22 dakika, 8 farklı kamera açısı, slayt geçişleri arası
- **Hedef:** 7 dakikalık tek video, akıcı akış, alt yazılı

## Akış

### Adım 1 — Transkript

```
Sen: 0425 projesinin Timeline 03'ünden transkript çıkar

Claude → transcript-agent çağrılır
       → scripts/extract_audio.py ile timeline-doğru ses
       → scripts/transcribe.py ile Whisper turbo
       → ~/Desktop/transcript_t03.json + .txt
```

**Süre:** ~3 dakika  (turbo modeli ilk kez 1.5 GB indirme dahil)

### Adım 2 — Kes listesi (21 dk → 5 dk)

```
Sen: bu transkripti 5 dakikaya indirmek için kes listesi çıkar

Claude → cut-list-agent çağrılır
       → tekrar/dolgu/sapma analizi
       → 14 kesim bloğu, sondan başa uygulanacak
       → ~/Desktop/mcp_kes_listesi.md
```

**Süre:** ~30 saniye

### Adım 3 — CapCut'ta uygula

Kullanıcı manuel: 14 kesim, sondan başa, ortalama 5 dakika iş.

### Adım 4 — Final timeline'dan altyazı

```
Sen: timeline 01'in altyazısını çıkar, sözlük düzeltmesiyle

Claude → subtitle-agent çağrılır
       → transcript-agent (word timestamps ile)
       → make_srt.py + AI/dev sözlüğü
       → ~/Desktop/mcp_video_altyazi.srt
```

Düzeltilen örnekler:
- "Sermen Kocabi" → "Selma Kocabıyık"
- "Cloud Code" → "Claude Code"  (her bağımlı ekiyle)
- "Versal" → "Vercel"
- "X kod" → "Xcode"
- "Antropik" → "Anthropic"
- "MTP" → "MCP"

**Süre:** ~3 dakika

### Adım 5 — YouTube açıklaması + bölümler

```
Sen: bu videoma YouTube description yaz, bölüm zaman damgaları da ekle

Claude → description-agent çağrılır
       → konu geçişlerini tespit eder
       → 9 bölüm (Intro / MCP Nedir / vs.)
       → kullanıcının önceki video stili referansıyla yapılandırır
       → ~/Desktop/youtube_description_mcp.md
```

**Süre:** ~30 saniye

### Adım 6 — X thread

```
Sen: bunun X thread'ini yaz

Claude → social-agent çağrılır
       → 10 tweet thread + alternatif uzun-form Article
       → ~/Desktop/x_post_mcp.md
```

**Süre:** ~30 saniye

## Toplam

| Adım | Manuel | Bu kit ile |
|------|--------|----------|
| Transkript | 60+ dk (yazıya dökmek) | 3 dk |
| Kes listesi | 90 dk (defalarca dinleme + not) | 30 sn |
| Altyazı | 60+ dk | 3 dk |
| YouTube açıklaması | 30 dk | 30 sn |
| X thread | 20 dk | 30 sn |
| **Toplam** | **~4-5 saat** | **~10 dakika** |

(CapCut'ta kesim uygulama süresi her ikisinde de aynı, ~5 dk)

## Çıktı kalitesi notu

Otomatize edilen kısımlar **deterministik script'ler** + **odaklı LLM agent'ları**.
Sözlük düzeltmesi regex tabanlı, agent'lar prompt-based. Sonuçların %95+'ı doğrudan
kullanılabilir; %5 manuel düzeltme genelde kişisel marka tercihleri (emoji sayısı,
hashtag tercihi vb.).

## Bu örnek nasıl yeniden üretilir?

Bu repo'da örnek dosyaları paylaşmıyoruz (kullanıcı verisi). Ama yapı aynı:

1. Kendi CapCut projeni hazırla
2. Claude Code'u repo dizininde aç (`cd video-production-kit && claude`)
3. Yukarıdaki diyalogları sırayla yaz
4. Çıktılar `~/Desktop/`'a düşer
