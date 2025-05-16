import requests
import os
import random
import time
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import io
import json

# --- Data Fetching from OpenLibrary ---

def fetch_book_details(book_key):
    """Fetches detailed information for a book using its OpenLibrary key."""
    if not book_key:
        return None, "No key provided"
    try:
        detail_url = f"https://openlibrary.org{book_key}.json"
        res = requests.get(detail_url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            description = "Not available."
            desc_obj = data.get("description")
            if isinstance(desc_obj, str):
                description = desc_obj
            elif isinstance(desc_obj, dict) and "value" in desc_obj:
                description = desc_obj["value"]
            
            # Extract other details if needed, e.g., more specific subjects, ISBNs
            # For now, primarily focusing on description.
            return {"description": description}, None
        else:
            return None, f"Failed to fetch details, status: {res.status_code}"
    except requests.RequestException as e:
        return None, f"Request exception for details: {e}"

def fetch_random_books(n):
    books_data = []
    tries = 0
    # Optimized max_tries: (n // 5 usable books per API call on average) + 20 buffer
    # Assuming limit=50 and roughly 10% to 20% usable results per page (i.e., 5-10 books)
    # This means for n books, we might need n/5 to n/10 API calls.
    # max_tries gives a ceiling.
    max_tries = (n // 5) + 20  # More reasonable max_tries
    if n == 1: # Ensure at least a few tries for a single book if n is very small
        max_tries = max(max_tries, 10)


    print("Fetching book data from OpenLibrary...")
    
    # Use a set to avoid duplicate book processing if keys are repeated in search results
    processed_keys = set()

    with requests.Session() as session: # Use a session for potential keep-alive benefits
        while len(books_data) < n and tries < max_tries:
            tries += 1
            page = random.randint(1, 500) # Reduced page range for potentially more relevant results
            try:
                search_url = f"https://openlibrary.org/search.json?q=language:eng&subject_facet=Fiction&subject_facet=Non-fiction&sort=random&limit=20&page={page}"
                res = session.get(search_url, timeout=15)
                
                if res.status_code != 200:
                    print(f"API request failed with status {res.status_code}, retrying...", end="\\r")
                    time.sleep(0.5)
                    continue
                
                docs = res.json().get("docs", [])
                random.shuffle(docs)
                
                for doc in docs:
                    if len(books_data) >= n:
                        break

                    book_key = doc.get("key")
                    if not book_key or book_key in processed_keys:
                        continue # Skip if no key or already processed

                    if "cover_i" in doc and "title" in doc:
                        processed_keys.add(book_key)
                        
                        # Basic info from search
                        book_info = {
                            "title": doc.get("title", "Unknown Title"),
                            "cover_id": doc["cover_i"],
                            "cover_url_large": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-L.jpg",
                            "cover_url_medium": f"https://covers.openlibrary.org/b/id/{doc['cover_i']}-M.jpg",
                            "authors": doc.get("author_name", ["Unknown Author"]),
                            "openlibrary_key": book_key,
                            "subjects_from_ol": doc.get("subject", []),
                            "isbn": doc.get("isbn", []) # Fetch ISBNs
                        }
                        
                        # Fetch more details (like description)
                        details, error_msg = fetch_book_details(book_key)
                        if details:
                            book_info.update(details)
                        else:
                            book_info["description"] = "Description not found or error fetching."
                            # print(f"Could not fetch details for {book_info['title']}: {error_msg}")

                        books_data.append(book_info)
                        print(f"Found {len(books_data)}/{n} books... (Attempt {tries})", end="\\r")

                time.sleep(0.2) # Politeness delay
            except requests.exceptions.Timeout:
                print(f"Request timed out on attempt {tries}, retrying...", end="\\r")
                time.sleep(1)
            except requests.RequestException as e:
                print(f"Request failed on attempt {tries}: {e}, retrying...", end="\\r")
                time.sleep(0.5)
            except json.JSONDecodeError:
                print(f"JSON decode error on attempt {tries}, skipping page...", end="\\r")
                time.sleep(0.5)

    print(f"\\nFinished fetching. Found {len(books_data)} books after {tries} tries.")
    if not books_data and tries >= max_tries:
        print("Could not fetch any books after maximum tries.")
    return books_data

# --- Tkinter GUI Application ---

class BookManagerApp:
    def __init__(self, master, books_data_list):
        self.master = master
        master.title("Book Data Manager")
        master.geometry("1000x750")

        self.books_data_list = books_data_list
        self.current_book_index = 0
        
        # Store user inputs for each book if needed, for now, we focus on current book export
        self.current_form_data = {} 

        if not self.books_data_list:
            messagebox.showinfo("No Books", "No books were fetched to display.")
            master.destroy()
            return

        self._init_vars()
        self._setup_ui()
        self.load_book_data(self.current_book_index)

    def _init_vars(self):
        """Initialize Tkinter variables for form fields."""
        self.title_var = tk.StringVar()
        self.author_var = tk.StringVar()
        self.condition_var = tk.StringVar(value="Good")
        self.book_type_var = tk.StringVar(value="For Sale")
        self.status_var = tk.StringVar(value="available")
        self.users_permissions_user_var = tk.StringVar()
        self.price_var = tk.StringVar()
        self.subject_for_strapi_var = tk.StringVar()
        self.course_var = tk.StringVar()
        self.exchange_var = tk.StringVar()
        self.featured_var = tk.BooleanVar(value=False)
        self.book_of_week_var = tk.BooleanVar(value=False)
        self.book_of_year_var = tk.BooleanVar(value=False)
        self.display_title_var = tk.StringVar()
        self.display_strapi_var = tk.BooleanVar(value=False) # For 'Display' field
        self.rating_var = tk.IntVar(value=0)
        self.categories_strapi_ids_var = tk.StringVar() # Comma-separated IDs
        self.cover_strapi_id_var = tk.StringVar()
        
        self.description_text_widget = None # Will be tk.Text
        self.ol_subjects_var = tk.StringVar()


    def _setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Layout: Left (Cover + OL Info), Right (User Input Fields)
        left_pane = ttk.Frame(main_frame, width=350)
        left_pane.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_pane.pack_propagate(False) 

        right_pane = ttk.Frame(main_frame)
        right_pane.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # --- Left Pane: Cover and OpenLibrary Info ---
        self.cover_label = ttk.Label(left_pane, text="Cover loading...")
        self.cover_label.pack(pady=10, anchor=tk.N)

        ol_info_frame = ttk.LabelFrame(left_pane, text="OpenLibrary Info", padding="10")
        ol_info_frame.pack(fill=tk.X, pady=10, anchor=tk.N)

        ttk.Label(ol_info_frame, text="Title:").grid(row=0, column=0, sticky=tk.W)
        self.ol_title_label = ttk.Label(ol_info_frame, text="", wraplength=300)
        self.ol_title_label.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(ol_info_frame, text="Authors:").grid(row=1, column=0, sticky=tk.W)
        self.ol_authors_label = ttk.Label(ol_info_frame, text="", wraplength=300)
        self.ol_authors_label.grid(row=1, column=1, sticky=tk.W, pady=2)
        
        ttk.Label(ol_info_frame, text="OL Subjects:").grid(row=2, column=0, sticky=tk.W)
        self.ol_subjects_label = ttk.Label(ol_info_frame, textvariable=self.ol_subjects_var, wraplength=300, justify=tk.LEFT)
        self.ol_subjects_label.grid(row=2, column=1, sticky=tk.W, pady=2)

        # --- Right Pane: User Input Fields (Scrollable) ---
        canvas = tk.Canvas(right_pane)
        scrollbar = ttk.Scrollbar(right_pane, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Fields Frame
        fields_frame = ttk.LabelFrame(scrollable_frame, text="Book Details for Strapi", padding="10")
        fields_frame.pack(fill=tk.X, expand=True)

        row_idx = 0
        # Helper for creating field rows
        def add_field(label_text, widget_type, var, options=None, **kwargs):
            nonlocal row_idx
            ttk.Label(fields_frame, text=label_text).grid(row=row_idx, column=0, sticky=tk.W, padx=5, pady=3)
            if widget_type == "Entry":
                widget = ttk.Entry(fields_frame, textvariable=var, width=40, **kwargs)
            elif widget_type == "Combobox":
                widget = ttk.Combobox(fields_frame, textvariable=var, values=options, state="readonly", width=38, **kwargs)
            elif widget_type == "Checkbutton":
                widget = ttk.Checkbutton(fields_frame, variable=var, **kwargs)
            elif widget_type == "Spinbox":
                widget = ttk.Spinbox(fields_frame, textvariable=var, from_=0, to=5, width=5, state="readonly", **kwargs)
            elif widget_type == "Text": # For description
                widget = tk.Text(fields_frame, width=50, height=8, wrap=tk.WORD, **kwargs)
                # Add scrollbar for Text widget
                text_scrollbar = ttk.Scrollbar(fields_frame, orient=tk.VERTICAL, command=widget.yview)
                widget.configure(yscrollcommand=text_scrollbar.set)
                widget.grid(row=row_idx, column=1, sticky=tk.EW, padx=5, pady=3, columnspan=2)
                text_scrollbar.grid(row=row_idx, column=3, sticky=tk.NS)
                row_idx +=1
                return widget # Return early as grid is custom
            else:
                raise ValueError(f"Unsupported widget type: {widget_type}")
            
            widget.grid(row=row_idx, column=1, sticky=tk.EW, padx=5, pady=3, columnspan=2)
            row_idx += 1
            return widget

        # Add fields using the helper
        add_field("Title (for Strapi):", "Entry", self.title_var)
        add_field("Author (for Strapi):", "Entry", self.author_var) # Usually from OL, but editable
        
        self.description_text_widget = add_field("Description (for Strapi):", "Text", None) # No variable for Text widget directly

        add_field("Condition:", "Combobox", self.condition_var, ["New", "Like New", "Good", "Fair", "Poor", "Digital Copy"])
        add_field("Book Type:", "Combobox", self.book_type_var, ["For Sale", "For Swap"])
        add_field("Status:", "Combobox", self.status_var, ["available", "pending", "sold"])
        add_field("Strapi User ID (owner):", "Entry", self.users_permissions_user_var)
        add_field("Price (if For Sale):", "Entry", self.price_var)
        add_field("Subject (Primary for Strapi):", "Entry", self.subject_for_strapi_var)
        add_field("Course:", "Entry", self.course_var)
        add_field("Exchange Details (if For Swap):", "Entry", self.exchange_var)
        add_field("Display Title (if different):", "Entry", self.display_title_var)
        add_field("Strapi Categories IDs (comma-sep):", "Entry", self.categories_strapi_ids_var)
        add_field("Strapi Cover Media ID:", "Entry", self.cover_strapi_id_var)
        add_field("Rating (0-5):", "Spinbox", self.rating_var)
        
        # Checkbuttons in their own subframe for better layout if many
        bool_frame = ttk.Frame(fields_frame)
        bool_frame.grid(row=row_idx, column=0, columnspan=3, sticky=tk.W, pady=5)
        ttk.Checkbutton(bool_frame, text="Featured", variable=self.featured_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(bool_frame, text="Book of Week", variable=self.book_of_week_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(bool_frame, text="Book of Year", variable=self.book_of_year_var).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(bool_frame, text="Display (Strapi 'Display')", variable=self.display_strapi_var).pack(side=tk.LEFT, padx=5)
        row_idx +=1

        # --- Control Buttons ---
        controls_frame = ttk.Frame(self.master, padding="10")
        controls_frame.pack(fill=tk.X, side=tk.BOTTOM)

        ttk.Button(controls_frame, text="Previous", command=self.prev_book).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="Next", command=self.next_book).pack(side=tk.LEFT, padx=5)
        self.nav_label = ttk.Label(controls_frame, text="")
        self.nav_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(controls_frame, text="Export Data for Strapi (Console)", command=self.export_book_data).pack(side=tk.RIGHT, padx=5)


    def load_book_data(self, index):
        if not (0 <= index < len(self.books_data_list)):
            return

        self.current_book_index = index
        book = self.books_data_list[index]

        # Update OL Info
        self.ol_title_label.config(text=book.get("title", "N/A"))
        self.ol_authors_label.config(text=", ".join(book.get("authors", ["N/A"])))
        
        ol_subjects_str = ", ".join(book.get("subjects_from_ol", [])[:5]) # Show first 5 subjects
        if len(book.get("subjects_from_ol", [])) > 5:
            ol_subjects_str += "..."
        self.ol_subjects_var.set(ol_subjects_str if ol_subjects_str else "N/A")

        self.display_cover(book.get("cover_url_medium")) # Use medium cover for display

        # Update form fields (pre-fill from book data)
        self.title_var.set(book.get("title", ""))
        self.author_var.set(", ".join(book.get("authors", [])))
        
        self.description_text_widget.delete("1.0", tk.END)
        self.description_text_widget.insert("1.0", book.get("description", ""))

        # Set defaults for user-input fields (or load from a saved state if implemented)
        self.condition_var.set("Good")
        self.book_type_var.set("For Sale")
        self.status_var.set("available")
        self.users_permissions_user_var.set("") # User must fill
        self.price_var.set("")
        
        # Try to pick a primary subject from OL subjects
        primary_subject = book.get("subjects_from_ol", [])[0] if book.get("subjects_from_ol") else ""
        self.subject_for_strapi_var.set(primary_subject)
        
        self.course_var.set("")
        self.exchange_var.set("")
        self.featured_var.set(False)
        self.book_of_week_var.set(False)
        self.book_of_year_var.set(False)
        self.display_title_var.set("")
        self.display_strapi_var.set(False)
        self.rating_var.set(0)
        self.categories_strapi_ids_var.set("")
        self.cover_strapi_id_var.set("")

        self.nav_label.config(text=f"Book {index + 1} of {len(self.books_data_list)}")


    def display_cover(self, cover_url):
        if not cover_url:
            self.cover_label.config(image=None, text="No cover URL")
            return

        try:
            # In a real app, consider threading for network requests to not freeze GUI
            response = requests.get(cover_url, timeout=10)
            response.raise_for_status() # Raise an exception for bad status codes
            
            image_data = response.content
            image = Image.open(io.BytesIO(image_data))
            
            # Resize image to fit label (e.g., max height 250px, maintain aspect ratio)
            max_h = 250
            img_w, img_h = image.size
            aspect_ratio = img_w / img_h
            new_h = min(img_h, max_h)
            new_w = int(new_h * aspect_ratio)
            image = image.resize((new_w, new_h), Image.Resampling.LANCZOS)

            photo_image = ImageTk.PhotoImage(image)
            
            self.cover_label.config(image=photo_image, text="")
            self.cover_label.image = photo_image # Keep a reference!
        except requests.RequestException as e:
            self.cover_label.config(image=None, text=f"Cover DL Error: {type(e).__name__}")
        except Exception as e: # Catch PIL errors or others
            self.cover_label.config(image=None, text=f"Cover Load Error: {type(e).__name__}")


    def next_book(self):
        if self.current_book_index < len(self.books_data_list) - 1:
            # Could save current form state here if needed for persistence between nav
            self.current_book_index += 1
            self.load_book_data(self.current_book_index)
        else:
            messagebox.showinfo("Navigation", "This is the last book.")

    def prev_book(self):
        if self.current_book_index > 0:
            # Could save current form state here
            self.current_book_index -= 1
            self.load_book_data(self.current_book_index)
        else:
            messagebox.showinfo("Navigation", "This is the first book.")

    def export_book_data(self):
        if not self.books_data_list:
            messagebox.showerror("Error", "No book data to export.")
            return

        current_ol_book = self.books_data_list[self.current_book_index]

        # Collect data from form fields
        data_payload = {
            "title": self.title_var.get(),
            "author": self.author_var.get(), # Assuming author string is fine
            "condition": self.condition_var.get(),
            "bookType": self.book_type_var.get(),
            "status": self.status_var.get(),
            "description": self.description_text_widget.get("1.0", tk.END).strip(),
            "featured": self.featured_var.get(),
            "bookOfWeek": self.book_of_week_var.get(),
            "bookOfYear": self.book_of_year_var.get(),
            "Display": self.display_strapi_var.get(), # Case-sensitive 'Display'
            "rating": self.rating_var.get()
        }

        # Fields that need type conversion or specific handling
        try:
            user_id_str = self.users_permissions_user_var.get()
            if user_id_str:
                data_payload["users_permissions_user"] = int(user_id_str)
            else: # This field is required as per your spec, handle if empty
                messagebox.showwarning("Input Error", "Strapi User ID (owner) is required.")
                return


            price_str = self.price_var.get()
            if self.book_type_var.get() == "For Sale":
                if price_str:
                    data_payload["price"] = float(price_str)
                else: # Price can be 0 or null if not for sale/free.
                    data_payload["price"] = 0.0 # Or None, depending on API
            elif "price" in data_payload: # remove if not for sale and was set
                 del data_payload["price"]


            categories_str = self.categories_strapi_ids_var.get()
            if categories_str:
                data_payload["categories"] = [int(cat_id.strip()) for cat_id in categories_str.split(',') if cat_id.strip()]
            
            cover_id_str = self.cover_strapi_id_var.get()
            if cover_id_str:
                data_payload["cover"] = int(cover_id_str)

        except ValueError as e:
            messagebox.showerror("Input Error", f"Invalid number format for User ID, Price, Categories, or Cover ID: {e}")
            return

        # Optional fields if not empty
        if self.subject_for_strapi_var.get():
            data_payload["subject"] = self.subject_for_strapi_var.get()
        if self.course_var.get():
            data_payload["course"] = self.course_var.get()
        if self.book_type_var.get() == "For Swap" and self.exchange_var.get():
            data_payload["exchange"] = self.exchange_var.get()
        if self.display_title_var.get():
            data_payload["displayTitle"] = self.display_title_var.get()
        
        # Add some OpenLibrary info for reference, not part of Strapi payload directly unless mapped
        # data_payload["_openlibrary_key"] = current_ol_book.get("openlibrary_key")
        # data_payload["_isbn"] = current_ol_book.get("isbn")


        final_json_output = {"data": data_payload}
        
        print("\\n--- Data for Strapi (Book: {}) ---".format(current_ol_book.get("title")))
        print(json.dumps(final_json_output, indent=2))
        messagebox.showinfo("Exported", "Book data for Strapi printed to console.")


# Original function, can be used separately if needed for bulk downloads
def download_covers_to_folder(books_data_list, folder_name="downloaded_book_covers"):
    if not books_data_list:
        print("No book data provided to download_covers_to_folder.")
        return

    os.makedirs(folder_name, exist_ok=True)
    total = len(books_data_list)
    print(f"\\nStarting download of {total} covers to '{folder_name}' folder...")
    
    for i, book in enumerate(books_data_list, 1):
        cover_url = book.get("cover_url_large")
        if not cover_url:
            print(f"[{i}/{total}] Skipping {book.get('title', 'Unknown Title')} - No cover URL.")
            continue

        try:
            res = requests.get(cover_url, timeout=15)
            percent = int((i / total) * 100)
            if res.status_code == 200:
                # Sanitize filename
                safe_title = "".join(c if c.isalnum() else "_" for c in book.get('title', 'Unknown_Title')[:50])
                filename = f"{folder_name}/{i}_{safe_title}.jpg"
                with open(filename, "wb") as f:
                    f.write(res.content)
                print(f"[{percent}%] Downloaded: {book.get('title', 'Unknown Title')}")
            else:
                print(f"[{percent}%] Failed: {book.get('title', 'Unknown Title')} (Status: {res.status_code})")
        except requests.exceptions.Timeout:
            print(f"[{percent}%] Timeout downloading cover for: {book.get('title', 'Unknown Title')}")
        except requests.RequestException as e:
            print(f"[{percent}%] Error for {book.get('title', 'Unknown Title')}: {e}")
        time.sleep(0.05)
    print("\\n✅ Cover download to folder finished.")


def main():
    try:
        # For testing, fetch a small number of books
        num_books_to_fetch = input("How many random books do you want to fetch for the GUI? (e.g., 5-10): ")
        count = int(num_books_to_fetch)
        if count <= 0:
            print("Please enter a positive number.")
            return

        fetched_books = fetch_random_books(count)
        
        if not fetched_books:
            print("No book data was fetched. Exiting.")
            return
        
        # --- Start GUI ---
        root = tk.Tk()
        app = BookManagerApp(root, fetched_books)
        root.mainloop()
        
        print("\\n✅ Script finished.")

    except ValueError:
        print("Invalid input. Please enter a number.")
    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()