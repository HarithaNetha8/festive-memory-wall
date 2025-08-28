import streamlit as st
from supabase import create_client
import uuid
import os

# Load Supabase credentials
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
SUPABASE_BUCKET = st.secrets["SUPABASE_BUCKET"]

# Initialize Supabase client
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

st.set_page_config(page_title="Festive Memory Wall", layout="wide")
st.title("🎉 Festive Memory Wall")
st.write("Preserve and share India's diverse festival traditions.")

menu = ["Upload Memory", "View Memories"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Upload Memory":
    st.subheader("Upload Your Festival Memory")
    festival_name = st.text_input("Festival Name")
    location = st.text_input("Location")
    description = st.text_area("Description")
    image_file = st.file_uploader("Upload Image", type=["jpg", "jpeg", "png"])

    if st.button("Submit"):
        if festival_name and location and image_file:
            try:
                # Generate unique filename
                file_ext = os.path.splitext(image_file.name)[1]
                file_name = f"{uuid.uuid4()}{file_ext}"

                # ✅ Convert image to bytes and upload
                file_bytes = image_file.read()
                supabase.storage.from_(SUPABASE_BUCKET).upload(file_name, file_bytes, {"content-type": image_file.type})


                # Generate public URL
                image_url = f"{SUPABASE_URL}/storage/v1/object/public/{SUPABASE_BUCKET}/{file_name}"

                # Insert data into Supabase table
                supabase.table("memories").insert({
                    "festival_name": festival_name,
                    "location": location,
                    "description": description,
                    "image_url": image_url
                }).execute()

                st.success("✅ Memory uploaded successfully!")
            except Exception as e:
                st.error(f"Error: {e}")
        else:
            st.warning("Please fill all fields and upload an image.")

elif choice == "View Memories":
    st.subheader("All Festival Memories")
    search = st.text_input("Search by Festival or Location")

    try:
        # Fetch data
        response = supabase.table("memories").select("*").order("created_at", desc=True).execute()
        data = response.data

        if search:
            data = [d for d in data if search.lower() in d['festival_name'].lower() or search.lower() in d['location'].lower()]

        if data:
            cols = st.columns(3)
            for idx, memory in enumerate(data):
                with cols[idx % 3]:
                    st.image(memory['image_url'], use_container_width=True)
                    st.write(f"**{memory['festival_name']}** - {memory['location']}")
                    st.caption(memory['description'])
        else:
            st.info("No memories found.")
    except Exception as e:
        st.error(f"Error fetching data: {e}")
