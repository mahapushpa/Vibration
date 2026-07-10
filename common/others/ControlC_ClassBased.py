import tkinter as tk
import signal

class TkApp:
    def __init__(self):
        self.root = tk.Tk()
        self.running = True  # Flag to track application state
        
        # Handle SIGINT (Ctrl+C in terminal) to close Tkinter window
        signal.signal(signal.SIGINT, self.handle_exit)
        
        # Schedule a periodic task (expandable for other periodic tasks)
        self.root.after(500, self.periodic_task)

        # Bind Ctrl+C in GUI to close the window
        self.root.bind_all("<Control-c>", lambda e: self.handle_exit())

    def periodic_task(self):
        """Scheduled task that runs every 500ms."""
        if self.running:
            print("Running periodic task...")  # Placeholder for future functionality
            self.root.after(500, self.periodic_task)

    def handle_exit(self, *args):
        """Gracefully exit the application."""
        print("Gracefully exiting...")
        self.running = False  # Update flag to stop tasks
        self.root.quit()  # Quit Tkinter event loop

    def run(self):
        """Start the Tkinter event loop."""
        try:
            print("Starting application...")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.handle_exit()

if __name__ == "__main__":
    app = TkApp()
    app.run()
    print("Application has exited gracefully.")
