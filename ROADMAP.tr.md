# Yol haritası

vmagents için planlananlar, kabaca sırasıyla. Fikir ve istekler issue olarak
gelebilir. English: [ROADMAP.md](ROADMAP.md).

## Şimdi

- [ ] `install.ps1` ve `tools`'u (Scoop) gerçek bir Windows 10'da denemek

## Sırada

- [ ] **Maliyet**: her görevin maliyeti (Claude Code bildiriyor), VM ve ay
      başına toplam, görev başına sınır (`run --max-cost 2`)
- [ ] **Görev kuyruğu**: bir VM için birkaç görev, art arda yapılır
- [ ] **Etikete göre issue'lar**: `vmagents fix dev --label vmagents` o
      etiketli açık issue'ların hepsini sırayla ele alır
- [ ] **Terminal arayüzünde görevler**: VM'in görevleri, durumları ve
      çıktılarıyla bir sekme (`runs` gibi)

## Daha sonra

- [ ] Windows VM'lerinde projeler ve `fix`
- [ ] Başka bir bilgisayarın VM'leri (SSH üzerinden bir libvirt sunucusu) aynı listede
- [ ] AUR paketinin yayımlanması (bir AUR hesabı gerekiyor)
- [ ] Gerçek kullanım turu: vmagents'ı gerçek bir projede baştan sona kullanıp
      takılan yerleri düzeltmek

## Son yapılanlar

- [x] `vmagents deps` (Debian, Ubuntu, Fedora, Arch, openSUSE, Alpine), Windows
      bilgisayar için `install.ps1`, VM'e araç kuran `vmagents tools` (Linux, Scoop ile Windows) (0.24.0)
- [x] `vmagents update`: vmagents'ı son sürüme günceller (0.23.0)
- [x] Telefona bildirimler, ntfy ile: biten görevler ve issue çözmeler,
      bekleyen yardımcılar, hazır olan yeni VM'ler (0.23.0)
- [x] Telefon sayfası yenilendi: yeni görünüm (açık ve koyu), görev verip
      izleme, issue çözdürme, VM başlatıp kapatma, ana ekranda uygulama gibi,
      aynı Wi-Fi'da internet gerekmez (0.22.0)
- [x] `vmagents fix`: GitHub issue'sundan pull request'e, testler VM'de
      çalışarak (0.22.0)
- [x] Telefon: VM'lerin telefonun tarayıcısında, SSH uygulamaları (0.21.0)
- [x] Windows VM'lerinde görevler (0.21.0)
- [x] Şablonlar, Claude'un geçmiş oturumları, arayüzde yük sütunu (0.19.0, 0.20.0)
- [x] `.deb` paketi, AUR dosyaları (0.18.0)
- [x] Kısıtlı ağ (0.17.0)
- [x] `try`: bir görev, VM'in birkaç kopyasında (0.16.0)
- [x] Sormadan çalışma ve görevler (`run`, `runs`) (0.15.0)
