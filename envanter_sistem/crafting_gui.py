import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk
import os
import json
from itertools import permutations

class CraftingRecipeGUI:
    """Crafting tarifleri eklemek için GUI arayüzü"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Crafting Tarif Ekleyici - 2x2 Grid")
        self.root.configure(bg="#2b2b2b")
        self.root.geometry("750x650")
        
        # Mevcut blokları yükle
        self.available_blocks = self.load_available_blocks()
        
        # Crafting grid slotları (2x2)
        self.grid_slots = [None, None, None, None]  # 4 slot
        
        # Output slot
        self.output_block = None
        self.output_count = 1
        
        # Mevcut tarifler
        self.recipes = self.load_recipes()
        
        # Rastgele permütasyon tik durumu
        self.randomize_var = tk.BooleanVar()
        
        self.setup_ui()
    
    def load_available_blocks(self):
        """assets/blocks klasöründeki blokları yükle"""
        blocks_dir = "assets/blocks"
        if not os.path.exists(blocks_dir):
            return []
        
        blocks = []
        for item in os.listdir(blocks_dir):
            item_path = os.path.join(blocks_dir, item)
            if os.path.isdir(item_path):
                blocks.append(item)
        
        return sorted(blocks)
    
    def load_recipes(self):
        """Mevcut tarifleri yükle"""
        recipe_file = "crafting_recipes.json"
        if os.path.exists(recipe_file):
            try:
                with open(recipe_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_recipes(self):
        """Tarifleri kaydet"""
        recipe_file = "crafting_recipes.json"
        try:
            with open(recipe_file, 'w', encoding="utf-8") as f:
                json.dump(self.recipes, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            messagebox.showerror("Hata", f"Tarifler kaydedilemedi:\n{e}")
            return False
    
    def setup_ui(self):
        """UI elemanlarını oluştur"""
        # Başlık
        title = tk.Label(
            self.root,
            text="🔨 Crafting Tarif Ekleyici (2x2)",
            bg="#2b2b2b",
            fg="white",
            font=("Segoe UI", 14, "bold")
        )
        title.pack(pady=10)
        
        # Ana frame
        main_frame = tk.Frame(self.root, bg="#2b2b2b")
        main_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # Sol panel - Crafting Grid
        left_panel = tk.Frame(main_frame, bg="#2b2b2b")
        left_panel.pack(side=tk.LEFT, padx=10)
        
        grid_label = tk.Label(
            left_panel,
            text="Crafting Grid (2x2)",
            bg="#2b2b2b",
            fg="#9fc5ff",
            font=("Segoe UI", 10, "bold")
        )
        grid_label.pack(pady=5)
        
        # 2x2 Grid
        grid_frame = tk.Frame(left_panel, bg="#1e1e1e", padx=10, pady=10)
        grid_frame.pack()
        
        self.grid_buttons = []
        for row in range(2):
            for col in range(2):
                idx = row * 2 + col
                btn = tk.Button(
                    grid_frame,
                    text="Boş",
                    width=12,
                    height=3,
                    bg="#3a3a3a",
                    fg="white",
                    command=lambda i=idx: self.select_grid_item(i)
                )
                btn.grid(row=row, column=col, padx=5, pady=5)
                self.grid_buttons.append(btn)
        
        # Temizle butonu
        clear_grid_btn = tk.Button(
            left_panel,
            text="🗑️ Grid'i Temizle",
            command=self.clear_grid,
            bg="#f44336",
            fg="white"
        )
        clear_grid_btn.pack(pady=10)
        
        # Orta panel - Ok işareti
        middle_panel = tk.Frame(main_frame, bg="#2b2b2b")
        middle_panel.pack(side=tk.LEFT, padx=20)
        
        arrow = tk.Label(
            middle_panel,
            text="→",
            bg="#2b2b2b",
            fg="white",
            font=("Arial", 30)
        )
        arrow.pack(pady=80)
        
        # Sağ panel - Output
        right_panel = tk.Frame(main_frame, bg="#2b2b2b")
        right_panel.pack(side=tk.LEFT, padx=10)
        
        output_label = tk.Label(
            right_panel,
            text="Çıktı (Output)",
            bg="#2b2b2b",
            fg="#9fc5ff",
            font=("Segoe UI", 10, "bold")
        )
        output_label.pack(pady=5)
        
        output_frame = tk.Frame(right_panel, bg="#1e1e1e", padx=10, pady=10)
        output_frame.pack()
        
        self.output_button = tk.Button(
            output_frame,
            text="Boş",
            width=12,
            height=3,
            bg="#3a3a3a",
            fg="white",
            command=self.select_output_item
        )
        self.output_button.pack(pady=5)
        
        # Miktar seçici
        count_frame = tk.Frame(output_frame, bg="#1e1e1e")
        count_frame.pack(pady=10)
        
        tk.Label(count_frame, text="Miktar:", bg="#1e1e1e", fg="white").pack(side=tk.LEFT)
        
        self.count_spinbox = tk.Spinbox(
            count_frame,
            from_=1,
            to=64,
            width=5,
            bg="#3a3a3a",
            fg="white"
        )
        self.count_spinbox.pack(side=tk.LEFT, padx=5)
        
        # Rastgele permütasyon tik kutusu
        random_check = tk.Checkbutton(
            output_frame,
            text="🌀 Grid rastgele permütasyonlu",
            variable=self.randomize_var,
            bg="#1e1e1e",
            fg="white",
            selectcolor="#2b2b2b"
        )
        random_check.pack(pady=5)
        
        # Alt panel - Butonlar
        bottom_frame = tk.Frame(self.root, bg="#2b2b2b")
        bottom_frame.pack(pady=10)
        
        # Craft olacak mı? butonu
        check_btn = tk.Button(
            bottom_frame,
            text="✓ Craft Olacak mı?",
            command=self.check_recipe,
            bg="#2196F3",
            fg="white",
            width=20,
            height=2
        )
        check_btn.pack(side=tk.LEFT, padx=5)
        
        # Tarif ekle butonu
        add_btn = tk.Button(
            bottom_frame,
            text="➕ Tarif Ekle",
            command=self.add_recipe,
            bg="#4caf50",
            fg="white",
            width=20,
            height=2
        )
        add_btn.pack(side=tk.LEFT, padx=5)
        
        # Tarifleri göster butonu
        show_btn = tk.Button(
            bottom_frame,
            text="📋 Tarifleri Göster",
            command=self.show_recipes,
            bg="#ff9800",
            fg="white",
            width=20,
            height=2
        )
        show_btn.pack(side=tk.LEFT, padx=5)
        
        # Bilgi
        info = tk.Label(
            self.root,
            text="Slot'lara tıklayarak blok seçin. 'Craft Olacak mı?' ile kontrol edin.",
            bg="#2b2b2b",
            fg="#cccccc",
            font=("Segoe UI", 9)
        )
        info.pack(pady=5)
    
    # --- Grid ve Output seçimleri ---
    def select_grid_item(self, index):
        if not self.available_blocks:
            messagebox.showwarning("Uyarı", "Hiç blok bulunamadı!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Slot {index+1} için blok seç")
        dialog.configure(bg="#2b2b2b")
        dialog.geometry("300x400")
        
        tk.Label(dialog, text="Blok Seçin (veya Boş için iptal)", bg="#2b2b2b", fg="white").pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=15, bg="#3a3a3a", fg="white")
        listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        for block in self.available_blocks:
            listbox.insert(tk.END, block)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                selected_block = self.available_blocks[selection[0]]
                self.grid_slots[index] = selected_block
                self.grid_buttons[index].config(text=selected_block, bg="#4caf50")
                dialog.destroy()
        
        def on_clear():
            self.grid_slots[index] = None
            self.grid_buttons[index].config(text="Boş", bg="#3a3a3a")
            dialog.destroy()
        
        btn_frame = tk.Frame(dialog, bg="#2b2b2b")
        btn_frame.pack(pady=10)
        
        tk.Button(btn_frame, text="Seç", command=on_select, bg="#4caf50", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Boş Yap", command=on_clear, bg="#f44336", fg="white").pack(side=tk.LEFT, padx=5)
    
    def select_output_item(self):
        if not self.available_blocks:
            messagebox.showwarning("Uyarı", "Hiç blok bulunamadı!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Çıktı bloğu seç")
        dialog.configure(bg="#2b2b2b")
        dialog.geometry("300x400")
        
        tk.Label(dialog, text="Çıktı Bloğu Seçin", bg="#2b2b2b", fg="white").pack(pady=10)
        
        listbox = tk.Listbox(dialog, height=15, bg="#3a3a3a", fg="white")
        listbox.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        for block in self.available_blocks:
            listbox.insert(tk.END, block)
        
        def on_select():
            selection = listbox.curselection()
            if selection:
                self.output_block = self.available_blocks[selection[0]]
                self.output_button.config(text=self.output_block, bg="#4caf50")
                dialog.destroy()
        
        tk.Button(dialog, text="Seç", command=on_select, bg="#4caf50", fg="white").pack(pady=10)
    
    def clear_grid(self):
        for i in range(4):
            self.grid_slots[i] = None
            self.grid_buttons[i].config(text="Boş", bg="#3a3a3a")
    
    # --- Tarif kontrol ---
    def get_recipe_key(self):
        return str(tuple(self.grid_slots))
    
    def check_recipe(self):
        key = self.get_recipe_key()
        if key in self.recipes:
            out = self.recipes[key]
            messagebox.showinfo("✓ Craft Olacak!", f"Tarif mevcut!\n{out['count']}x {out['output']}")
        else:
            messagebox.showinfo("✗ Craft Olmayacak", "Bu kombinasyon için tarif bulunamadı.")
    
    # --- Tarif ekleme ---
    def add_recipe(self):
        if self.randomize_var.get():
            self.add_randomized_recipe()
        else:
            self.add_single_recipe()
    
    def add_single_recipe(self):
        if not self.output_block:
            messagebox.showwarning("Uyarı", "Lütfen çıktı bloğu seçin!")
            return
        if all(slot is None for slot in self.grid_slots):
            messagebox.showwarning("Uyarı", "Lütfen en az bir slot doldurun!")
            return
        try:
            count = int(self.count_spinbox.get())
        except:
            messagebox.showerror("Hata", "Geçersiz miktar!")
            return
        
        key = self.get_recipe_key()
        self.recipes[key] = {'output': self.output_block, 'count': count}
        if self.save_recipes():
            messagebox.showinfo("Başarılı!", f"Tarif eklendi!\n{self.grid_slots} → {count}x {self.output_block}")
            self.update_python_code()
    
    def add_randomized_recipe(self):
        """Seçilen blokların tüm permütasyonlarını ekle"""
        if not self.output_block:
            messagebox.showwarning("Uyarı", "Lütfen çıktı bloğu seçin!")
            return
        if all(slot is None for slot in self.grid_slots):
            messagebox.showwarning("Uyarı", "En az bir slot doldurun!")
            return
        try:
            count = int(self.count_spinbox.get())
        except:
            messagebox.showerror("Hata", "Geçersiz miktar!")
            return
        
        blocks_to_permute = self.grid_slots.copy()
        all_perms = set(permutations(blocks_to_permute))
        added_count = 0
        for perm in all_perms:
            key = str(perm)
            if key not in self.recipes:
                self.recipes[key] = {'output': self.output_block, 'count': count}
                added_count += 1
        
        if self.save_recipes():
            messagebox.showinfo("Başarılı!", f"{added_count} permütasyon craft sistemine eklendi.")
            self.update_python_code()
    
    # --- Python kodu güncelleme ---
    def update_python_code(self):
        try:
            code_lines = [
                "# block_ekleme.py - OTOMATİK OLUŞTURULDU",
                "class CraftingRecipes:",
                "    def __init__(self):",
                "        self.recipes_2x2 = {"
            ]
            for recipe_key, out in self.recipes.items():
                grid = eval(recipe_key)
                code_lines.append(f"            {grid}: ('{out['output']}', {out['count']}),")
            code_lines.append("        }")
            code_lines.append("")
            code_lines.append("    def craft_olacak_mi(self, grid, grid_size=2):")
            code_lines.append("        if grid_size == 2:")
            code_lines.append("            return grid in self.recipes_2x2")
            code_lines.append("        return False")
            code_lines.append("")
            code_lines.append("    def get_craft_result(self, grid, grid_size=2):")
            code_lines.append("        if grid_size == 2 and grid in self.recipes_2x2:")
            code_lines.append("            return self.recipes_2x2[grid]")
            code_lines.append("        return None")
            
            with open("block_ekleme.py", "w", encoding="utf-8") as f:
                f.write("\n".join(code_lines))
            
            messagebox.showinfo("Başarılı", "block_ekleme.py dosyası güncellendi!")
        except Exception as e:
            messagebox.showerror("Hata", f"Python kodu güncellenemedi:\n{e}")
    
    # --- Tarifleri göster ---
    def show_recipes(self):
        if not self.recipes:
            messagebox.showinfo("Tarifler", "Henüz tarif eklenmemiş!")
            return
        
        dialog = tk.Toplevel(self.root)
        dialog.title("Mevcut Tarifler")
        dialog.configure(bg="#2b2b2b")
        dialog.geometry("500x400")
        
        tk.Label(dialog, text=f"Toplam {len(self.recipes)} Tarif", bg="#2b2b2b", fg="white", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        text = tk.Text(dialog, height=20, width=60, bg="#3a3a3a", fg="white")
        text.pack(pady=10, padx=20)
        
        for i, (recipe_key, out) in enumerate(self.recipes.items(), 1):
            grid = eval(recipe_key)
            text.insert(tk.END, f"{i}. {grid}\n   → {out['count']}x {out['output']}\n\n")
        text.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()
    app = CraftingRecipeGUI(root)
    root.mainloop()
