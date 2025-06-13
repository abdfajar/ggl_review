import streamlit as st
import requests
import pandas as pd
import re
import os
import time
import math

def sanitize_filename(name):
    return re.sub(r'[^a-zA-Z0-9_\-]', '_', name)

def haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # radius bumi dalam meter
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

def save_reviews(reviews, place_name, place_type, folder_path):
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
    review_folder = os.path.join(folder_path, "reviews")
    os.makedirs(review_folder, exist_ok=True)
    filename = f"{safe_type}_{safe_name}_reviews.csv"
    full_path = os.path.join(review_folder, filename)
    df_reviews.to_csv(full_path, index=False)
    return full_path

def app(lat, lng, keyword, city, api_key, filename, folder_path, max_results=100):
    lat = float(lat)
    lng = float(lng)

    places = search_places(lat, lng, keyword, api_key, max_results=max_results)
    os.makedirs(folder_path, exist_ok=True)

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

        save_reviews(reviews, name, types, folder_path)

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
    full_csv_path = os.path.join(folder_path, f"{safe_filename}.csv")
    df.to_csv(full_csv_path, index=False)

    st.success(f"✅ Data utama disimpan di: `{full_csv_path}`")
    st.success(f"📁 Review per tempat disimpan di folder: `{os.path.join(folder_path, 'reviews')}`")

    return df

# Streamlit App
st.set_page_config(page_title="Google Places Search Tool", layout="wide")
st.title("📍 Google Places Search Tool (Jarak + Review)")

st.markdown("""
Cari tempat terdekat berdasarkan keyword dan simpan hasilnya dalam CSV.  
Hasil termasuk informasi tambahan seperti website, nomor telepon, dan review.  
Jarak dihitung dari titik koordinat pusat.
""")

with st.form("search_form"):
    col1, col2 = st.columns(2)
    with col1:
        lat = st.text_input("Latitude", "")
        lng = st.text_input("Longitude", "")
        keyword = st.text_input("Keyword Pencarian", "klinik")
    with col2:
        city = st.text_input("Nama Kota", "")
        api_key = st.text_input("Google API Key", type="password")
        filename = st.text_input("Nama file hasil (tanpa .csv)", "hasil_cari")

    folder_path = st.text_input("📂 Path folder penyimpanan (contoh: /home/user/data)")
    submitted = st.form_submit_button("🔍 Jalankan Pencarian")

if submitted:
    if not folder_path:
        st.error("❗ Silakan isi path folder penyimpanan.")
    elif not (lat and lng and keyword and api_key and filename):
        st.error("❗ Semua field wajib diisi.")
    else:
        with st.spinner("Sedang mencari tempat..."):
            df_result = app(lat, lng, keyword, city, api_key, filename, folder_path)
            st.dataframe(df_result)
