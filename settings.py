import os

class Settings:
    def __init__(self):
        self.filename = "settings.txt"
        self.render_distance = 4
        self.load()

    def load(self):
        if not os.path.exists(self.filename):
            self.save()
            return

        try:
            with open(self.filename, "r") as f:
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=")
                        if key == "render_distance":
                            self.render_distance = int(value)
        except Exception as e:
            print(f"Error loading settings: {e}")

    def save(self):
        try:
            with open(self.filename, "w") as f:
                f.write(f"render_distance={self.render_distance}\n")
        except Exception as e:
            print(f"Error saving settings: {e}")
