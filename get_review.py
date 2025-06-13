import streamlit as st
import requests
import pandas as pd
import re
import os
import time
import math
from tkinter import Tk, filedialog

# Fungsi utilitas
def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Radius bumi dalam meter
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def search_places(lat, lng, keyword, api_key, max_results=100):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    session = requests.Session()
    location = f"{lat},{lng}"
    params = {
        "location": location,
        "keyword": keyword,
        "rankby": "distance",
        "key": api_key
    }
    all_results = []

    while len(all_results) < max_results:
        response = session.get(url, params=params)
        data = response.json()
        results = data.get("results", [])
        if results:
            all_results.extend(results)
        if 'next_page_token' in data:
            next_page_token = data['next_page_token']
            time.sleep(2)
            params = {
                "pagetoken": next_page_token,
                "key": api_key
            }
        else:
            break

    return all_results[:max_results]

def fetch_place_details(place_id, api_key):
    details_url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields = "formatted_phone_number,website,editorial_summary,reviews"
    params = {
        "place_id": place_id,
        "fields": fields,
        "key": api_key
    }
    response = requests.get(details_url, params=params)
    return response.json().get("result", {})

def save_reviews(reviews, place_name, place_type, drive_path):
    if not reviews:
        return None

    review_data = []
    for review in reviews:
        review_data.append({
            "Author": review.get("author_name"),
            "Rating": review.get("rating"),
            "Text": review.get("text"),
            "Time": review.get("relative_time_description")
        })

    df_reviews = pd.DataFrame(review_data)
    safe_type = sanitize_filename(place_type.split(',')[0] if place_type else 'place')
    safe_name = sanitize_filename(place_name)
    review_folder = os.path.join(drive_path, "reviews")
    os.makedirs(review_folder, exist_ok=True)
    filename = f"{safe_type}_{safe_name}_reviews.csv"
    full_path = os.path.join(review_folder, filename)
    df_reviews.to_csv(full_path, index=False)
    return full_path

def app(lat, lng, keyword, city, api_key, filename, drive_path, max_results=100):
    lat = float(lat)
    lng = float(lng)

    places = search_places(lat, lng, keyword, api_key, max_results=max_results)
    os.makedirs(drive_path, exist_ok=True)

    place_data = []

    for place in places:
        place_id = place.get("place_id")
        name = place.get("name")
        geometry = place.get("geometry", {}).get("location", {})
        place_lat = geometry.get("lat")
        place_lng = geometry.get("lng")
        types = ", ".join(place.get("types", []))
        rating = place.get("rating")
        vicinity = place.get("vicinity")
        distance_meters = haversine(lat, lng, place_lat, place_lng)

        details = fetch_place_details(place_id, api_key)
        phone = details.get("formatted_phone_number")
        website = details.get("website")
        summary = details.get("editorial_summary", {}).get("overview")
        reviews = details.get("reviews", [])
        review_snippet = reviews[0].get("text") if reviews else None

        save_reviews(reviews, name, types, drive_path)

        place_data.append([
            place_id, name, place_lat, place_lng, types, rating,
            vicinity, city, distance_meters, phone, website, summary, review_snippet
        ])

    df = pd.DataFrame(place_data, columns=[
        "Place ID", "Place Name", "Lat", "Long", "Type",
        "Rating", "Vicinity", "City", "Distance (meters)",
        "Phone", "Website", "Summary", "Review Snippet"
    ])

    safe_filename = sanitize_filename(filename)
    full_csv_path = os.path.join(drive_path, f"{safe_filename}.csv")
    df.to_csv(full_csv_path, index=False)

    st.success(f"📁 Data utama disimpan di: {full_csv_path}")
    st.info(f"💬 Review per tempat disimpan di folder: {os.path.join(drive_path, 'reviews')}")
    return df

# Fungsi pilih folder (lokal)
def pilih_folder():
    
    folder_path = filedialog.askdirectory()
   
    return folder_path

# Streamlit Interface
st.set_page_config(page_title="Google Places Search", layout="centered")
st.title("🗺️ Google Places Search Tool (Streamlit)")

lat = st.text_input("Latitude", "")
lng = st.text_input("Longitude", "")
keyword = st.text_input("Keyword (misal: rumah sakit, apotek)", "")
city = st.text_input("City", "")
api_key = st.text_input("Google API Key", type="password")
filename = st.text_input("Nama file untuk disimpan (tanpa .csv)")

if "folder_path" not in st.session_state:
    st.session_state["folder_path"] = ""

if st.button("📂 Pilih Folder Penyimpanan"):
    selected = pilih_folder()
    if selected:
        st.session_state["folder_path"] = selected
        st.success(f"Folder dipilih: {selected}")
    else:
        st.warning("Tidak ada folder yang dipilih.")

if st.button("🔍 Jalankan Pencarian"):
    if not st.session_state["folder_path"]:
        st.error("❗ Silakan pilih folder penyimpanan terlebih dahulu.")
    elif not (lat and lng and keyword and api_key and filename):
        st.error("❗ Semua field wajib diisi.")
    else:
        with st.spinner("Sedang mencari tempat..."):
            df_result = app(lat, lng, keyword, city, api_key, filename, st.session_state["folder_path"])
            st.success("Pencarian selesai.")
            st.dataframe(df_result)
