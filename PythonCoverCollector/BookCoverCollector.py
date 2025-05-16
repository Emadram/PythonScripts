import requests
import os
import json
import io
import traceback
from tkinter import ttk, messagebox
import tkinter as tk
from PIL import Image, ImageTk

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

def fetch_books_by_isbns(isbn_list):
    """
    Fetch book metadata and covers for a list of ISBNs using OpenLibrary's /search.json?isbn=... endpoint.
    Returns a list of book dicts (one per found ISBN).
    """
    if not isbn_list:
        return []
    # Remove duplicates and empty
    isbn_list = [isbn.strip() for isbn in isbn_list if isbn.strip()]
    if not isbn_list:
        return []
    
    books = []
    batch_size = 50 # OpenLibrary can handle many ISBNs in one query
    for i in range(0, len(isbn_list), batch_size):
        batch = isbn_list[i:i+batch_size]
        # Construct URL for batch ISBN query
        params = '&'.join(f'isbn={isbn}' for isbn in batch)
        url = f'https://openlibrary.org/search.json?{params}'
        print(f"Fetching batch: {url}") # DEBUG
        try:
            res = requests.get(url, timeout=20) # Increased timeout slightly
            print(f"Response status code: {res.status_code}") # DEBUG
            if res.status_code != 200:
                print(f"API Error for batch. Status: {res.status_code}, Response: {res.text[:200]}...") # DEBUG
                continue
            
            response_data = res.json()
            docs = response_data.get('docs', [])
            print(f"Found {len(docs)} docs in response for batch. numFound: {response_data.get('numFound')}, Batch size: {len(batch)}") # DEBUG

            if len(batch) == 1 and len(docs) == 1:
                doc = docs[0]
                queried_isbn_for_single_match = batch[0] # The ISBN we asked for
                print(f"Single batch item and single doc returned. Assuming doc (title: '{doc.get('title', 'N/A')}') is for ISBN {queried_isbn_for_single_match}.") # DEBUG
                
                # Use the queried_isbn_for_single_match as the definitive ISBN for this book record
                book = {
                    'title': doc.get('title', 'Unknown Title'),
                    'authors': doc.get('author_name', ['Unknown Author']),
                    'cover_url_medium': f'https://covers.openlibrary.org/b/isbn/{queried_isbn_for_single_match}-M.jpg',
                    'cover_url_large': f'https://covers.openlibrary.org/b/isbn/{queried_isbn_for_single_match}-L.jpg',
                    'subjects_from_ol': doc.get('subject', []),
                    'isbn': [queried_isbn_for_single_match], # Store the matched ISBN
                    'openlibrary_key': doc.get('key'),
                    'description': doc.get('first_sentence_value', doc.get('first_sentence', [f"Published: {doc.get('first_publish_year', 'N/A')}"])[0]) if doc.get('first_sentence_value') or doc.get('first_sentence') or doc.get('first_publish_year') else 'Description not available.',
                    'description_loaded': True
                }
                books.append(book)
            else:
                # Original logic for multi-item batches or when doc count doesn't match single batch item
                # This part still relies on finding ISBN in doc.seed or doc.isbn
                for doc in docs:
                    found_isbn_in_doc = None 
                    seeds = doc.get('seed', [])
                    for seed_item in seeds:
                        if isinstance(seed_item, str) and '/isbn/' in seed_item:
                            potential_isbn = seed_item.split('/isbn/')[-1]
                            if potential_isbn in batch:
                                found_isbn_in_doc = potential_isbn
                                print(f"Found ISBN {found_isbn_in_doc} from seed: {seed_item} for doc title: '{doc.get('title', 'N/A')}'") # DEBUG
                                break
                    
                    if not found_isbn_in_doc:
                        doc_isbns = doc.get('isbn', [])
                        if isinstance(doc_isbns, list):
                            for potential_isbn in doc_isbns:
                                if potential_isbn in batch:
                                    found_isbn_in_doc = potential_isbn
                                    print(f"Found ISBN {found_isbn_in_doc} from doc.isbn field for doc title: '{doc.get('title', 'N/A')}'") # DEBUG
                                    break
                                    
                    if not found_isbn_in_doc:
                        print(f"Skipping doc (title: '{doc.get('title', 'N/A')}'), no matching ISBN found via seed or doc.isbn that is in the current batch. Seeds: {seeds}, Doc ISBNs: {doc.get('isbn', [])}, Batch: {batch}") # DEBUG
                        continue

                    # Construct book dict using found_isbn_in_doc
                    book = {
                        'title': doc.get('title', 'Unknown Title'),
                        'authors': doc.get('author_name', ['Unknown Author']),
                        'cover_url_medium': f'https://covers.openlibrary.org/b/isbn/{found_isbn_in_doc}-M.jpg',
                        'cover_url_large': f'https://covers.openlibrary.org/b/isbn/{found_isbn_in_doc}-L.jpg',
                        'subjects_from_ol': doc.get('subject', []),
                        'isbn': [found_isbn_in_doc], 
                        'openlibrary_key': doc.get('key'),
                        'description': doc.get('first_sentence_value', doc.get('first_sentence', [f"Published: {doc.get('first_publish_year', 'N/A')}"])[0]) if doc.get('first_sentence_value') or doc.get('first_sentence') or doc.get('first_publish_year') else 'Description not available.',
                        'description_loaded': True
                    }
                    books.append(book)
        except requests.exceptions.Timeout as e:
            print(f"RequestTimeout for URL {url}: {e}") # DEBUG
            continue
        except requests.exceptions.RequestException as e:
            print(f"RequestException for URL {url}: {e}") # DEBUG
            continue
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError for URL {url}: {e}. Response text: {res.text[:200]}...") # DEBUG
            continue
        except Exception as e:
            print(f"Unexpected error processing batch for URL {url}: {e}") # DEBUG
            traceback.print_exc() # Print full traceback
            continue
    
    print(f"Finished fetching by ISBNs. Total books collected: {len(books)}") # DEBUG
    return books

# --- Tkinter GUI Application ---

class BookManagerApp:
    def __init__(self, master, books_data_list=None):
        self.master = master
        master.title("Book Data Manager")
        master.geometry("1000x800")

        # Initialize with an empty list, as books will be fetched via ISBN through UI
        self.books_data_list = [] 
        self.current_book_index = -1 # No book loaded initially
        self.current_form_data = {}

        self._init_vars()
        self._setup_ui()
        # Removed automatic loading of initial books_data_list
        # self.load_book_data will be called after fetching via ISBN
        if not self.books_data_list:
            self.nav_label.config(text="No books loaded. Use 'Fetch Books by ISBN'.")
            # Optionally, disable Next/Prev buttons if no books
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)

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

        self.isbn_input_var = tk.StringVar()


    def _setup_ui(self):
        # Main frame
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- ISBN Input Section ---
        isbn_frame = ttk.LabelFrame(main_frame, text="Fetch Books by ISBN", padding="10")
        isbn_frame.pack(fill=tk.X, pady=5)
        ttk.Label(isbn_frame, text="Enter ISBNs (comma or newline separated):").pack(anchor=tk.W)
        self.isbn_text = tk.Text(isbn_frame, height=3, width=60)
        self.isbn_text.pack(side=tk.LEFT, padx=5)
        ttk.Button(isbn_frame, text="Fetch Books", command=self.fetch_books_by_isbn).pack(side=tk.LEFT, padx=10)

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

        self.prev_button = ttk.Button(controls_frame, text="Previous", command=self.prev_book)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        self.next_button = ttk.Button(controls_frame, text="Next", command=self.next_book)
        self.next_button.pack(side=tk.LEFT, padx=5)
        self.nav_label = ttk.Label(controls_frame, text="")
        self.nav_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(controls_frame, text="Export Data for Strapi (Console)", command=self.export_book_data).pack(side=tk.RIGHT, padx=5)


    def load_book_data(self, index):
        if not self.books_data_list or not (0 <= index < len(self.books_data_list)):
            self.clear_form_and_display()
            self.nav_label.config(text="No book to display or index out of bounds.")
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
            return

        self.current_book_index = index
        book = self.books_data_list[index] # This is a reference to the dict in the list

        # Update OL Info
        self.ol_title_label.config(text=book.get("title", "N/A"))
        self.ol_authors_label.config(text=", ".join(book.get("authors", ["N/A"])))
        
        ol_subjects_str = ", ".join(book.get("subjects_from_ol", [])[:5]) 
        if len(book.get("subjects_from_ol", [])) > 5:
            ol_subjects_str += "..."
        self.ol_subjects_var.set(ol_subjects_str if ol_subjects_str else "N/A")

        self.display_cover(book.get("cover_url_medium")) 

        # Update form fields (pre-fill from book data)
        self.title_var.set(book.get("title", ""))
        self.author_var.set(", ".join(book.get("authors", [])))
        
        # Handle description loading on demand
        self.description_text_widget.delete("1.0", tk.END)
        if book.get("description_loaded"):
            self.description_text_widget.insert("1.0", book.get("description", "Not available."))
        else:
            self.description_text_widget.insert("1.0", "Loading description...")
            # Fetch description (this will block GUI briefly the first time)
            # In a more advanced app, this would be in a separate thread.
            details, error_msg = fetch_book_details(book.get("openlibrary_key"))
            if details:
                book["description"] = details.get("description", "Error fetching description.")
            else:
                book["description"] = f"Error fetching description: {error_msg}"
            book["description_loaded"] = True # Mark as loaded
            
            # Update the widget again with the fetched description
            self.description_text_widget.delete("1.0", tk.END)
            self.description_text_widget.insert("1.0", book.get("description"))

        # Set defaults for user-input fields 
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
        self.prev_button.config(state=tk.NORMAL if index > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if index < len(self.books_data_list) - 1 else tk.DISABLED)


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
        if not self.books_data_list:
            messagebox.showinfo("Navigation", "No books loaded. Fetch books by ISBN first.")
            return
        if self.current_book_index < len(self.books_data_list) - 1:
            # Could save current form state here if needed for persistence between nav
            self.current_book_index += 1
            self.load_book_data(self.current_book_index)
        else:
            messagebox.showinfo("Navigation", "This is the last book.")

    def prev_book(self):
        if not self.books_data_list:
            messagebox.showinfo("Navigation", "No books loaded. Fetch books by ISBN first.")
            return
        if self.current_book_index > 0:
            # Could save current form state here
            self.current_book_index -= 1
            self.load_book_data(self.current_book_index)
        else:
            messagebox.showinfo("Navigation", "This is the first book.")

    def export_book_data(self):
        if not self.books_data_list or self.current_book_index == -1:
            messagebox.showerror("Error", "No book data loaded or selected to export.")
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

    def fetch_books_by_isbn(self):
        isbn_string = self.isbn_text.get("1.0", tk.END).strip()
        if not isbn_string:
            messagebox.showwarning("Input Error", "Please enter one or more ISBNs.")
            return

        # Split by comma or newline, then strip whitespace and filter out empty strings
        isbn_list = [isbn.strip() for isbn_pattern in isbn_string.replace('\n', ',').split(',') for isbn in [isbn_pattern.strip()] if isbn]

        if not isbn_list:
            messagebox.showwarning("Input Error", "No valid ISBNs entered after parsing.")
            return

        print(f"User entered ISBNs for fetching: {isbn_list}") # Debug
        
        # Show a loading message or disable parts of UI
        self.nav_label.config(text="Fetching books by ISBN...")
        self.master.update_idletasks() # Force UI update

        fetched_books = fetch_books_by_isbns(isbn_list)

        if fetched_books:
            self.books_data_list = fetched_books
            self.current_book_index = 0 # Start at the first fetched book
            self.load_book_data(self.current_book_index)
            messagebox.showinfo("Success", f"Successfully fetched {len(fetched_books)} book(s).")
        else:
            self.books_data_list = []
            self.current_book_index = -1
            self.clear_form_and_display()
            self.nav_label.config(text="No books found for the provided ISBN(s).")
            messagebox.showwarning("Not Found", "No books found for the provided ISBN(s).")
        
        # Update button states based on whether books were loaded
        if self.books_data_list:
            self.prev_button.config(state=tk.DISABLED if len(self.books_data_list) <= 1 else tk.NORMAL)
            self.next_button.config(state=tk.DISABLED if len(self.books_data_list) <= 1 else tk.NORMAL)
            if len(self.books_data_list) == 1:
                 self.prev_button.config(state=tk.DISABLED)
                 self.next_button.config(state=tk.DISABLED)
        else:
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)

    def clear_form_and_display(self):
        """Clears all display fields and form inputs."""
        self.ol_title_label.config(text="N/A")
        self.ol_authors_label.config(text="N/A")
        self.ol_subjects_var.set("N/A")
        self.cover_label.config(image=None, text="No cover")
        self.cover_label.image = None # Clear reference

        self.title_var.set("")
        self.author_var.set("")
        if self.description_text_widget:
            self.description_text_widget.delete("1.0", tk.END)
        self.condition_var.set("Good")
        self.book_type_var.set("For Sale")
        self.status_var.set("available")
        self.users_permissions_user_var.set("")
        self.price_var.set("")
        self.subject_for_strapi_var.set("")
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
        self.nav_label.config(text="No books loaded.")


# Original function, can be used separately if needed for bulk downloads
def download_covers_to_folder(books_data_list, folder_name="downloaded_book_covers"):
    if not books_data_list:
        print("No book data provided to download_covers_to_folder.")
        return

    os.makedirs(folder_name, exist_ok=True)
    total = len(books_data_list)
    print(f"\nStarting download of {total} covers to '{folder_name}' folder...")
    
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
    print("\n✅ Cover download to folder finished.")


def main():
    # No longer pre-fetches random books
    root = tk.Tk()
    app = BookManagerApp(root) # Initialize without pre-fetched data
    root.mainloop()

if __name__ == "__main__":
    main()

def fetch_book_by_isbn(isbn): # This function is no longer used by the app but kept for potential direct use.
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            key = next(iter(data)) if data else None
            if key:
                return data[key]
    except Exception:
        return None

    # def fetch_books_by_isbn(self): # This method has been moved into the BookManagerApp class
    #     isbn_raw = self.isbn_text.get("1.0", tk.END)
    #     isbn_list = [isbn.strip() for isbn in isbn_raw.replace(',', '\\n').split('\\n') if isbn.strip()]
    #     if not isbn_list:
    #         messagebox.showwarning("Input Error", "Please enter at least one ISBN.")
    #         return
    #     books = fetch_books_by_isbns(isbn_list)
    #     if not books:
    #         messagebox.showinfo("No Books", "No valid books found for the provided ISBNs.")
    #         return
    #     self.books_data_list = books
    #     self.current_book_index = 0
    #     self.load_book_data(0)
    #     messagebox.showinfo("Done", f"Fetched {len(books)} books by ISBN.")