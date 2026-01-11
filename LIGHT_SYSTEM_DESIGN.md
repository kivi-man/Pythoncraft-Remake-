# Işık Sistemi Tasarım Dokümanı (Light System Design)

Bu doküman, voxel tabanlı oyun motoru için performans odaklı bir ışıklandırma sistemi tasarımını içerir.

## 1. Çalışma Mantığı (Logic)

Sistem, fiziksel ışık simülasyonu yerine "hücresel otomat" (cellular automata) benzeri bir yayılım mantığı kullanır.

1.  **Işık Türleri**:
    *   **BlockLight**: Yapay ışık kaynakları (Meşale, Lava, Glowstone). Kaynaktan uzaklaştıkça azalır.
    *   **SkyLight**: Güneş ışığı. Gökyüzünden dikey olarak iner, engelle karşılaşınca durur ve yanlara doğru azalır.
2.  **Değer Aralığı**: 0 (tam karanlık) ile 15 (tam parlak) arası tamsayılar.
3.  **Yayılım**:
    *   Bir blok ışık aldığında, 6 komşusuna (yukarı, aşağı, sağ, sol, ön, arka) bakar.
    *   Eğer komşu blok katı (opaque) değilse, komşunun ışık değeri `Mevcut Blok - 1` olacak şekilde güncellenir.
    *   Bu işlem ışık değeri 0 olana kadar devam eder.

## 2. Veri Yapıları (Data Structures)

Bellek kullanımını minimize etmek ve CPU önbellek (cache) verimliliğini artırmak için veriler sıkıştırılacaktır.

### Chunk Verisi

Her Chunk (veya Subchunk) blok ID'lerini sakladığı gibi ışık verilerini de saklamalıdır.
Mevcut `Chunk` sınıfına (veya `Subchunk`'a) yeni bir dizi eklenecektir.

*   **Yapı**: 1D Dizi (Flat Array) veya 3D Dizi. Python listeleri yerine `bytearray` veya `array` modülü kullanımı performans için kritiktir.
*   **Paketleme**: Her blok 2 ışık değerine sahiptir (Sky + Block). İkisi de 0-15 aralığındadır (4 bit).
    *   Tek bir 8-bit tamsayı (byte) içinde iki değer saklanabilir.
    *   **Format**: `(SkyLight << 4) | BlockLight`

```python
# Örnek Subchunk Veri Yapısı Taslağı
class Subchunk:
    def __init__(self):
        # ... diğer init kodları ...
        # 16x16x16 = 4096 blok
        # Her blok için 1 byte (2 nibble)
        self.light_map = bytearray(4096) 

    def get_light(self, x, y, z):
        index = x + y * 16 + z * 16 * 16 # Veya kullanılan indeksleme yöntemi
        val = self.light_map[index]
        return (val & 0xF, (val >> 4) & 0xF) # (Block, Sky)

    def set_light(self, x, y, z, block_light, sky_light):
        index = x + y * 16 + z * 16 * 16
        self.light_map[index] = (sky_light << 4) | (block_light & 0xF)
```

## 3. Flood Fill Algoritması (Pseudo-Code)

Işık yayılımı Breadth-First Search (BFS) kullanır.

### Işık Ekleme / Güncelleme Kuyruğu
```python
queue = CircularBuffer() # Veya deque

def propagate_light(source_queue):
    while not source_queue.empty():
        node = source_queue.pop()
        x, y, z, light_level = node
        
        # 6 Komşu için
        for nx, ny, nz in neighbors(x, y, z):
            # 1. Dünya sınırları ve Chunk yüklenme kontrolü
            if not is_valid(nx, ny, nz): continue
            
            # 2. Katı blok kontrolü (Işık geçmez)
            if is_opaque(nx, ny, nz): continue
            
            # 3. Mevcut ışık değerini al
            current_neighbor_light = get_light(nx, ny, nz)
            
            # 4. Eğer yeni ışık değeri (light_level - 1), komşunun mevcut ışığından büyükse güncelle
            if (light_level - 1) > current_neighbor_light:
                set_light(nx, ny, nz, light_level - 1)
                queue.push(nx, ny, nz, light_level - 1)
```

### Işık Silme (Örn: Meşale Kırıldı)
Silme işlemi biraz daha karmaşıktır. Önce ışığı "söndürürüz", sonra komşulardan geri besleme alırız.
1.  Kırılan bloktaki ışığı 0 yap.
2.  Etkilenen komşuları kuyruğa ekle.
3.  Eğer komşunun ışığı, bizim sildiğimiz ışıktan türemişse (yani `komşu == silinen - 1`), onu da sil ve yay.
4.  Eğer komşunun ışığı başka bir kaynaktan geliyorsa (yüksekse), onu "Işık Ekleme" kuyruğuna ekle ki geri doldursun.

## 4. Chunk Sınırlarında Güncelleme

Sistem "Sonsuz Dünya" veya çoklu chunk yapısında olduğu için ışık chunk sınırlarını geçebilir.

1.  **Global Koordinatlara Çeviri**: Algoritma Subchunk-local değil, World-global koordinatlarla (veya Chunk ID + Local Index) çalışmalıdır.
2.  **Komşu Chunk Erişimi**: `World` sınıfı üzerinden `get_block_light(global_x, ...)` metodu kullanılmalı.
3.  **Dirty Flag**: Eğer bir chunk'taki ışık güncellemesi, komşu chunk'ın sınır bloğunu etkilerse, komşu chunk'ın `modified` bayrağı (flag) `True` yapılır. Böylece komşu chunk'ın mesh'i de (GPU verisi) güncellenir.
    *   Örnek: Chunk A'nın en sağındaki blok (x=15) ışık alırsa, Chunk B'nin en solundaki blok (x=0) etkilenir. Chunk B de "re-mesh" edilmelidir.

## 5. Shader Entegrasyonu

GPU hesaplama yapmaz, sadece veriyi gösterir.

### Vertex Shader (`vert.glsl`)
Vertex yapısına yeni bir veri eklenir veya mevcut `shading_value` modifiye edilir. 
Öneri: `shading_value` zaten var (AO için kullanılıyor olabilir). Işık seviyesini bu değerle çarparak gönderebiliriz.

```glsl
layout(location = 2) in float shading_value; // Mevcut (AO/Face Shade)
layout(location = 3) in float light_level;   // YENİ: 0.0 - 1.0 arası normalize edilmiş

out float v_light;

void main() {
    // ... pozisyon işlemleri ...
    v_light = light_level; 
    // Veya ikisini birleştirip tek varying kullanabiliriz:
    // v_shading = shading_value * light_level;
}
```

### Fragment Shader (`frag.glsl`)
```glsl
in float v_light;
uniform sampler2D tex;

void main() {
    vec4 texColor = texture(tex, uv);
    
    // Formül: finalColor = baseColor * (lightLevel / 15.0)
    // CPU'dan light_level zaten 0-1 arasına bölünmüş geliyorsa:
    // float brightness = v_light; 
    
    // Gama (Opsiyonel):
    float brightness = pow(v_light, 1.3);
    
    // Tam karanlığı engellemek için minimum bir ortam ışığı (ambient) eklenebilir
    // brightness = max(brightness, 0.05);

    color = vec4(texColor.rgb * brightness, texColor.a);
}
```

### Mesh Oluşturma (CPU Tarafı - `chunk.py`)
Mesh oluşturulurken (Geometry Building):
1.  Yüzün baktığı bloğun ışık seviyesini al (Kendi bloğunun değil!).
    *   Eğer yüzey (Face) `(x, y, z)` deki bloğun `TOP` yüzü ise, `(x, y+1, z)` deki bloğun ışık seviyesini al.
2.  Bu değeri 0-15 arasından 0.0-1.0 arasına normalize et.
3.  Vertex verisine ekle.

## 6. Performans Nedenleri

1.  **GPU Yükü Yok**: Işık hesaplaması tamamen CPU'da ve sadece değişiklik olduğunda yapılır. GPU her karede (60 FPS) ışık hesabı yapmaz, sadece statik bir float ile çarpma işlemi yapar.
2.  **Byte Paketleme**: Python'da tamsayılar (integer) object'tir ve çok yer kaplar. `bytearray` kullanımı milyonlarca bloğu 4-5 MB içinde tutmayı sağlar, CPU cache miss oranını düşürür.
3.  **Local Updates**: Sadece ışık kaynağı değiştiğinde ve sadece etkilenen alan (BFS'nin ulaştığı yer) güncellenir. Tüm dünya taranmaz.
4.  **Bitwise Operasyonlar**: `(light >> 4)` gibi işlemler matematiksel işlemlerden (`/`, `%`) çok daha hızlıdır.
