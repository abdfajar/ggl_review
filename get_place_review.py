import streamlit as st
import requests
import pandas as pd
import re
import os
import time
import math
import zipfile
from io import BytesIO

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius bumi dalam meter
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def search_places(lat, lng, keyword, api_key, max_results=100):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    session = requests.Session()
    location = f"{lat},{lng}"
    params = {"location": location, "keyword": keyword, "rankby": "distance", "key": api_key}
    all_results = []

    while len(all_results) < max_results:
        response = session.get(url, params=params)
        data = response.json()
        results = data.get("results", [])
        all_results.extend(results)

        if 'next_page_token' in data:
            time.sleep(2)
            params = {"pagetoken": data['next_page_token'], "key": api_key}
        else:
            break

    return all_results[:max_results]

def fetch_place_details(place_id, api_key):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    fields = "formatted_phone_number,website,editorial_summary,reviews"
    params = {"place_id": place_id, "fields": fields, "key": api_key}
    response = requests.get(url, params=params)
    return response.json().get("result", {})

def save_reviews(reviews, place_name, place_type, folder_path):
    if not reviews:
        return None
    review_data = []
    for r in reviews:
        review_data.append({
            "Author": r.get("author_name"),
            "Rating": r.get("rating"),
            "Text": r.get("text"),
            "Time": r.get("relative_time_description")
        })
    df = pd.DataFrame(review_data)
    safe_type = sanitize_filename(place_type.split(',')[0] if place_type else 'place')
    safe_name = sanitize_filename(place_name)
    review_folder = os.path.join(folder_path, "reviews")
    os.makedirs(review_folder, exist_ok=True)
    filepath = os.path.join(review_folder, f"{safe_type}_{safe_name}_reviews.csv")
    df.to_csv(filepath, index=False)
    return filepath

def compress_folder(folder_path, zip_name):
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder_path)
                zipf.write(full_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

def app(lat, lng, keyword, city, filename, max_results=100):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        st.error("❗ GOOGLE_API_KEY belum diatur di environment.")
        return None

    lat = float(lat)
    lng = float(lng)

    folder_path = os.path.expanduser("~/google_places_data")
    os.makedirs(folder_path, exist_ok=True)

    places = search_places(lat, lng, keyword, api_key, max_results=max_results)

    place_data = []

    for place in places:
        place_id = place.get("place_id")
        name = place.get("name")
        geo = place.get("geometry", {}).get("location", {})
        place_lat, place_lng = geo.get("lat"), geo.get("lng")
        types = ", ".join(place.get("types", []))
        rating = place.get("rating")
        vicinity = place.get("vicinity")
        distance = haversine(lat, lng, place_lat, place_lng)
        details = fetch_place_details(place_id, api_key)
        phone = details.get("formatted_phone_number")
        website = details.get("website")
        summary = details.get("editorial_summary", {}).get("overview")
        reviews = details.get("reviews", [])

        save_reviews(reviews, name, types, folder_path)

        place_data.append([
            place_id, name, place_lat, place_lng, types, rating,
            vicinity, city, distance, phone, website, summary
        ])

    df = pd.DataFrame(place_data, columns=[
        "Place ID", "Place Name", "Lat", "Long", "Type", "Rating", "Vicinity",
        "City", "Distance (meters)", "Phone", "Website", "Summary"
    ])

    safe_filename = sanitize_filename(filename)
    csv_path = os.path.join(folder_path, f"{safe_filename}.csv")
    df.to_csv(csv_path, index=False)

    zip_buffer = compress_folder(folder_path, f"{safe_filename}.zip")

    st.success("✅ Pencarian selesai dan hasil telah disimpan serta dikompresi.")
    st.download_button("⬇️ Unduh File ZIP", data=zip_buffer, file_name=f"{safe_filename}.zip", mime="application/zip")

    return df

# === Streamlit UI ===
st.set_page_config(page_title="Google Places Review Collector", layout="wide")
st.title("📍 Google Places Review Collector (otomatis simpan & kompres)")

st.markdown("""
Masukkan koordinat dan keyword pencarian. Sistem akan mencari tempat terdekat, 
mengambil detail & review, lalu menyimpan ke folder `~/google_places_data`, 
dan hasilnya otomatis dikompresi ke ZIP.
""")

with st.form("form"):
    col1, col2 = st.columns(2)
    with col1:
        lat = st.text_input("Latitude", "")
        lng = st.text_input("Longitude", "")
        keyword = st.text_input("Keyword (misal: klinik, warung)", "klinik")
    with col2:
        city = st.text_input("Nama Kota", "")
        filename = st.text_input("Nama File Utama", "hasil_pencarian")

    run = st.form_submit_button("🔍 Jalankan")

if run:
    if not all([lat, lng, keyword, city, filename]):
        st.warning("❗ Semua input wajib diisi.")
    else:
        with st.spinner("Sedang memproses data..."):
            df = app(lat, lng, keyword, city, filename)
            if df is not None:
                st.dataframe(df)
