import os
import random
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- APP CONFIGURATION ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = "affms_secret_key_change_in_production"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'affms.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- DATABASE MODELS ---
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), nullable=False)

class PondBatch(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pond_name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(100), nullable=False)
    initial_count = db.Column(db.Integer, nullable=False)
    current_count = db.Column(db.Integer, nullable=False)
    avg_weight_grams = db.Column(db.Float, nullable=False)
    stocking_date = db.Column(db.String(50), nullable=False)

    @property
    def case_survival_rate(self):
        if self.initial_count == 0: return 0.0
        return round((self.current_count / self.initial_count) * 100, 1)

    @property
    def biomass_kg(self):
        return round((self.current_count * self.avg_weight_grams) / 1000, 1)

class WaterLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.String(50), nullable=False)
    pond_name = db.Column(db.String(100), nullable=False)
    ph = db.Column(db.Float, nullable=False)
    dissolved_oxygen = db.Column(db.Float, nullable=False)
    temp_celsius = db.Column(db.Float, nullable=False)
    ammonia = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False)

class FeedInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stock_kg = db.Column(db.Float, nullable=False)
    threshold_kg = db.Column(db.Float, nullable=False)

# --- EMBEDDED FRONTEND TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AFFMS - Aquaculture Management System</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-slate-100 text-slate-800 font-sans min-h-screen flex flex-col relative">

    <!-- [AFFMS_07_04] POP-OUT NOTIFICATION TOAST -->
    {% if toast_msg %}
    <div id="toast-popup" class="fixed top-5 right-5 z-50 {% if 'WARNING' in toast_msg %}bg-amber-900 border-amber-500{% else %}bg-slate-900 border-teal-500{% endif %} text-white px-5 py-3.5 rounded-xl shadow-2xl flex items-center gap-3 border transition-all transform duration-300">
        <div class="p-1.5 {% if 'WARNING' in toast_msg %}bg-amber-500 text-slate-900{% else %}bg-teal-500 text-slate-900{% endif %} rounded-lg font-bold">
            {% if 'WARNING' in toast_msg %}⚠️{% else %}✓{% endif %}
        </div>
        <div>
            <p class="font-bold text-xs {% if 'WARNING' in toast_msg %}text-amber-400{% else %}text-teal-400{% endif %}">
                {% if 'WARNING' in toast_msg %}Telemetry Alert{% else %}System Alert{% endif %}
            </p>
            <p class="text-xs text-slate-200">{{ toast_msg }}</p>
        </div>
        <button onclick="document.getElementById('toast-popup').remove()" class="ml-4 text-slate-400 hover:text-white text-lg font-bold">&times;</button>
    </div>
    <script>
        setTimeout(() => {
            const toast = document.getElementById('toast-popup');
            if(toast) {
                toast.style.opacity = '0';
                setTimeout(() => toast.remove(), 300);
            }
        }, 4500);
    </script>
    {% endif %}

    <!-- HEADER -->
    <header class="bg-teal-700 text-white p-4 shadow-md flex justify-between items-center">
        <div class="flex items-center gap-3">
            <div class="p-2 bg-teal-800 rounded-lg">
                <svg class="w-6 h-6 text-teal-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/>
                </svg>
            </div>
            <div>
                <h1 class="text-xl font-bold leading-none">AFFMS</h1>
                <p class="text-[11px] text-teal-200 mt-0.5">Aquaculture & Fish Farm Management System</p>
            </div>
        </div>

        {% if current_user %}
        <div class="flex items-center gap-3">
            <div class="text-right text-xs">
                <p class="font-bold text-white">{{ current_user.name }}</p>
                <p class="text-teal-200 text-[10px]">{{ current_user.role }}</p>
            </div>
            <!-- [AFFMS_03_05] LOGOUT -->
            <a href="/logout" class="bg-teal-800 hover:bg-teal-900 text-teal-100 text-xs px-3 py-1.5 rounded border border-teal-600 transition">
                Logout
            </a>
        </div>
        {% endif %}
    </header>

    {% if current_user %}
    <!-- SUB-HEADER WITH TABS & LIVE SEARCH BAR -->
    <div class="bg-white border-b shadow-sm px-6 py-3 flex flex-col md:flex-row justify-between items-center gap-4">
        <!-- NAVIGATION TABS -->
        <nav class="flex gap-6 font-semibold text-sm text-slate-600">
            <button onclick="switchTab('overview')" id="tab-overview" class="hover:text-teal-600 pb-1 border-b-2 border-teal-600 text-teal-600 transition">Overview Dashboard</button>
            <button onclick="switchTab('ponds')" id="tab-ponds" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Ponds & Batches</button>
            <button onclick="switchTab('water')" id="tab-water" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Water Quality</button>
            <button onclick="switchTab('feed')" id="tab-feed" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Feed & Inventory</button>
        </nav>

        <!-- [AFFMS_07_03] LIVE SEARCH BAR -->
        <div class="relative w-full md:w-72">
            <input type="text" id="searchInput" onkeyup="filterAllData()" placeholder="🔍 Search pond, species, feed..." class="w-full border border-slate-300 rounded-lg px-3 py-1.5 text-xs focus:ring-2 focus:ring-teal-500 bg-slate-50">
        </div>
    </div>
    {% endif %}

    <!-- MAIN CONTAINER -->
    <main class="p-4 md:p-6 max-w-7xl mx-auto w-full flex-grow">

        {% if not current_user %}
        <!-- AUTHENTICATION MODULE (REGISTER / LOGIN / RESET) -->
        <section class="flex justify-center items-center py-6">
            <div class="bg-white p-8 rounded-xl shadow-md border border-slate-200 max-w-md w-full space-y-5">

                <!-- NOTIFICATION ALERTS -->
                {% if auth_error %}
                <div class="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-3 rounded-lg font-medium">
                    {{ auth_error }}
                </div>
                {% endif %}

                {% if auth_success %}
                <div class="bg-emerald-50 border border-emerald-200 text-emerald-700 text-xs p-3 rounded-lg font-medium">
                    {{ auth_success }}
                </div>
                {% endif %}

                <!-- [AFFMS_01] REGISTER ADMIN FORM -->
                <div id="auth-register-box" class="space-y-4 {% if auth_view != 'register' %}hidden{% endif %}">
                    <div class="text-center space-y-1">
                        <h2 class="text-2xl font-bold text-slate-800">Register Admin Account</h2>
                        <p class="text-xs text-slate-500">Create a new Farm Manager administrative account</p>
                    </div>

                    <form action="/register" method="POST" class="space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Full Name</label>
                            <input type="text" name="name" placeholder="Kok Jie" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Email Address</label>
                            <input type="email" name="email" placeholder="admin@affms.com" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Password (Decided by User)</label>
                            <input type="password" name="password" placeholder="Min 6 characters" minlength="6" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div class="bg-teal-50 border border-teal-200 p-2.5 rounded-lg text-[11px] text-teal-800">
                            🛡️ <strong>Assigned Role:</strong> Farm Manager (System Admin Access)
                        </div>
                        <button type="submit" class="w-full bg-teal-700 hover:bg-teal-800 text-white font-semibold py-2.5 rounded-lg text-sm shadow transition">
                            Register Admin Account
                        </button>
                    </form>

                    <div class="border-t pt-4 text-center text-xs text-slate-500">
                        Already have an account? 
                        <button onclick="showAuthBox('login')" class="text-teal-700 font-bold hover:underline">Sign In</button>
                    </div>
                </div>

                <!-- [AFFMS_02] LOGIN FORM -->
                <div id="auth-login-box" class="space-y-4 {% if auth_view != 'login' %}hidden{% endif %}">
                    <div class="text-center space-y-1">
                        <h2 class="text-2xl font-bold text-slate-800">Sign In to AFFMS</h2>
                        <p class="text-xs text-slate-500">Access farm telemetry and batch management</p>
                    </div>

                    <form action="/login" method="POST" class="space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Email Address</label>
                            <input type="email" name="email" placeholder="admin@affms.com" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div>
                            <div class="flex justify-between items-center mb-1">
                                <label class="text-xs font-semibold text-slate-600">Password</label>
                                <button type="button" onclick="showAuthBox('reset')" class="text-xs text-teal-600 hover:underline">Forgot password?</button>
                            </div>
                            <input type="password" name="password" placeholder="••••••••" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <button type="submit" class="w-full bg-teal-700 hover:bg-teal-800 text-white font-semibold py-2.5 rounded-lg text-sm shadow transition">
                            Sign In
                        </button>
                    </form>

                    <div class="border-t pt-4 text-center text-xs text-slate-500">
                        Don't have an account? 
                        <button onclick="showAuthBox('register')" class="text-teal-700 font-bold hover:underline">Register Admin Account</button>
                    </div>
                </div>

                <!-- [AFFMS_03] RESET PASSWORD FORM -->
                <div id="auth-reset-box" class="space-y-4 {% if auth_view != 'reset' %}hidden{% endif %}">
                    <div class="text-center space-y-1">
                        <h2 class="text-2xl font-bold text-slate-800">Reset Password</h2>
                        <p class="text-xs text-slate-500">Enter your registered email and choose a new password</p>
                    </div>

                    <form action="/reset-password" method="POST" class="space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Registered Email Address</label>
                            <input type="email" name="email" placeholder="your-email@affms.com" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">New Password</label>
                            <input type="password" name="new_password" placeholder="New password" minlength="6" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Confirm New Password</label>
                            <input type="password" name="confirm_password" placeholder="Confirm new password" minlength="6" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                        </div>
                        <button type="submit" class="w-full bg-teal-700 hover:bg-teal-800 text-white font-semibold py-2.5 rounded-lg text-sm shadow transition">
                            Update Password
                        </button>
                    </form>

                    <div class="border-t pt-4 text-center text-xs text-slate-500">
                        Remembered your password? 
                        <button onclick="showAuthBox('login')" class="text-teal-700 font-bold hover:underline">Back to Sign In</button>
                    </div>
                </div>

            </div>
        </section>

        {% else %}

        <!-- [AFFMS_07_01 & AFFMS_07_02] 1. OVERVIEW DASHBOARD -->
        <section id="sec-overview" class="space-y-6">
            <h2 class="text-xl font-bold text-slate-800">Farm Overview & Telemetry</h2>
            
            <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-white p-4 rounded-xl shadow-sm border-l-4 border-teal-500">
                    <p class="text-xs font-medium text-slate-500">Active Ponds</p>
                    <p class="text-2xl font-bold mt-1">{{ batches|length }}</p>
                </div>
                <div class="bg-white p-4 rounded-xl shadow-sm border-l-4 border-emerald-500">
                    <p class="text-xs font-medium text-slate-500">Total Live Fish</p>
                    <p class="text-2xl font-bold mt-1">{{ total_fish }}</p>
                </div>
                <div class="bg-white p-4 rounded-xl shadow-sm border-l-4 border-blue-500">
                    <p class="text-xs font-medium text-slate-500">Water Quality Status</p>
                    <p class="text-2xl font-bold text-emerald-600 mt-1">Optimal</p>
                </div>
                <div class="bg-white p-4 rounded-xl shadow-sm border-l-4 border-amber-500">
                    <p class="text-xs font-medium text-slate-500">Total Feed Stock</p>
                    <p class="text-2xl font-bold text-slate-800 mt-1">{{ total_feed }} kg</p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div class="bg-white p-5 rounded-xl shadow-sm border md:col-span-2">
                    <h3 class="font-bold text-sm text-slate-700 mb-4">Water Quality Trends (pH & DO)</h3>
                    <div class="h-64"><canvas id="chartWaterTrends"></canvas></div>
                </div>
                <div class="bg-white p-5 rounded-xl shadow-sm border">
                    <h3 class="font-bold text-sm text-slate-700 mb-4">Stock Breakdown by Species</h3>
                    <div class="h-64 flex justify-center"><canvas id="chartSpecies"></canvas></div>
                </div>
            </div>
        </section>

        <!-- [AFFMS_04] 2. PONDS & FISH BATCH LIFECYCLE -->
        <section id="sec-ponds" class="hidden space-y-6">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-slate-800">Pond & Fish Batch Lifecycle Management</h2>
                <button onclick="document.getElementById('modalBatch').classList.remove('hidden')" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 text-sm font-semibold">
                    + Register New Batch
                </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="batchContainer">
                {% for b in batches %}
                <div class="searchable-card bg-white p-5 rounded-xl shadow-sm border space-y-3" data-search="{{ b.pond_name }} {{ b.species }}">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="text-lg font-bold text-slate-800">{{ b.pond_name }} ({{ b.species }})</h3>
                            <p class="text-xs text-slate-500">Stocked: {{ b.stocking_date }}</p>
                        </div>
                        <span class="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-1 rounded-full font-semibold">{{ b.case_survival_rate }}% Survival</span>
                    </div>
                    <!-- [AFFMS_04_02] AUTOMATED CALCULATIONS -->
                    <div class="grid grid-cols-3 gap-2 text-center text-xs bg-slate-50 p-3 rounded-lg">
                        <div>
                            <span class="block text-slate-400">Current Count</span>
                            <span class="font-bold text-slate-700">{{ b.current_count }}</span>
                        </div>
                        <div>
                            <span class="block text-slate-400">Avg Weight</span>
                            <span class="font-bold text-slate-700">{{ b.avg_weight_grams }}g</span>
                        </div>
                        <div>
                            <span class="block text-slate-400">Est. Biomass</span>
                            <span class="font-bold text-teal-700">{{ b.biomass_kg }} kg</span>
                        </div>
                    </div>
                    <div class="flex justify-end gap-2 pt-1">
                        <button onclick="openEditBatchModal('{{ b.id }}', '{{ b.pond_name }}', '{{ b.species }}', '{{ b.initial_count }}', '{{ b.current_count }}', '{{ b.avg_weight_grams }}', '{{ b.stocking_date }}')" class="text-xs text-teal-700 hover:text-teal-900 px-3 py-1 rounded bg-teal-50 font-semibold border border-teal-200">✏️ Edit</button>
                        <a href="/batch/delete/{{ b.id }}" onclick="return confirm('Delete this batch?')" class="text-xs text-rose-600 hover:text-rose-800 px-3 py-1 rounded bg-rose-50 font-semibold border border-rose-200">Delete</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- [AFFMS_05] 3. WATER QUALITY MONITORING & AUTOMATION -->
        <section id="sec-water" class="hidden space-y-6">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-slate-800">Water Quality Telemetry & Automated Sensor System</h2>
                <!-- [AFFMS_05_05] AUTOMATED IoT SENSOR SCAN ENGINE -->
                <form action="/water/auto-scan" method="POST" class="inline">
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow flex items-center gap-1.5 transition">
                        🤖 Run Auto-Sensor Telemetry Scan
                    </button>
                </form>
            </div>

            <!-- [AFFMS_05_01] MANUAL LOGGING FORM -->
            <div class="bg-white p-5 rounded-xl shadow-sm border space-y-4">
                <h3 class="font-bold text-sm text-slate-700">Log Daily Water Parameter Reading</h3>
                <form action="/water/add" method="POST" class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Target Pond</label>
                        <select name="pond_name" class="w-full border rounded-lg p-2 text-sm" required>
                            {% for b in batches %}
                            <option value="{{ b.pond_name }}">{{ b.pond_name }} ({{ b.species }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">pH (6.5 - 8.5)</label>
                        <input type="number" step="0.1" name="ph" value="7.2" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">DO (≥ 5.0 mg/L)</label>
                        <input type="number" step="0.1" name="dissolved_oxygen" value="6.5" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Temp (25 - 32°C)</label>
                        <input type="number" step="0.1" name="temp_celsius" value="27.5" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Ammonia (≤ 0.05 ppm)</label>
                        <input type="number" step="0.01" name="ammonia" value="0.02" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div class="sm:col-span-2 md:col-span-5 text-right">
                        <button type="submit" class="bg-teal-600 text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-teal-700">Save Reading</button>
                    </div>
                </form>
            </div>

            <div class="bg-white p-5 rounded-xl shadow-sm border space-y-3">
                <h3 class="font-bold text-sm text-slate-700">Recent Environmental Logs</h3>
                <div class="overflow-x-auto">
                    <table class="w-full text-left text-sm">
                        <thead class="bg-slate-50 border-b">
                            <tr>
                                <th class="p-3">Time</th>
                                <th class="p-3">Pond Name</th>
                                <th class="p-3">pH</th>
                                <th class="p-3">Oxygen</th>
                                <th class="p-3">Temp (°C)</th>
                                <th class="p-3">Ammonia (ppm)</th>
                                <th class="p-3">Status</th>
                                <th class="p-3 text-right">Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for l in water_logs %}
                            <tr class="searchable-row border-b hover:bg-slate-50" data-search="{{ l.pond_name }} {{ l.status }}">
                                <td class="p-3 font-medium">{{ l.timestamp }}</td>
                                <td class="p-3">{{ l.pond_name }}</td>
                                <!-- [AFFMS_05_04] BOLD AMBER HIGHLIGHTING FOR BREACHED VALUES -->
                                <td class="p-3 {% if l.ph < 6.5 or l.ph > 8.5 %}text-amber-600 font-bold{% endif %}">{{ l.ph }}</td>
                                <td class="p-3 {% if l.dissolved_oxygen < 5.0 %}text-amber-600 font-bold{% endif %}">{{ l.dissolved_oxygen }}</td>
                                <td class="p-3 {% if l.temp_celsius < 25.0 or l.temp_celsius > 32.0 %}text-amber-600 font-bold{% endif %}">{{ l.temp_celsius }}°C</td>
                                <td class="p-3 {% if l.ammonia > 0.05 %}text-amber-600 font-bold{% endif %}">{{ l.ammonia }}</td>
                                <td class="p-3">
                                    <span class="px-2 py-0.5 rounded text-xs font-semibold {% if l.status == 'Safe' %}bg-emerald-100 text-emerald-800{% else %}bg-amber-100 text-amber-800{% endif %}">
                                        {{ l.status }}
                                    </span>
                                </td>
                                <td class="p-3 text-right flex justify-end gap-2">
                                    <button onclick="openEditWaterModal('{{ l.id }}', '{{ l.pond_name }}', '{{ l.ph }}', '{{ l.dissolved_oxygen }}', '{{ l.temp_celsius }}', '{{ l.ammonia }}')" class="text-xs text-teal-700 hover:text-teal-900 px-2.5 py-1 bg-teal-50 border border-teal-200 rounded font-semibold">✏️ Edit</button>
                                    <a href="/water/delete/{{ l.id }}" onclick="return confirm('Delete this water quality log?')" class="text-xs text-rose-600 hover:text-rose-800 px-2.5 py-1 bg-rose-50 border border-rose-200 rounded font-semibold">Delete</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- [AFFMS_06] 4. FEED INVENTORY & AUTOMATED DISPENSER -->
        <section id="sec-feed" class="hidden space-y-6">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-slate-800">Feed Inventory & Automated Dispenser Engine</h2>
                <!-- [AFFMS_06_04] AUTOMATED FEED DISPENSER ENGINE -->
                <form action="/feed/auto-dispense" method="POST" class="inline">
                    <button type="submit" class="bg-amber-600 hover:bg-amber-700 text-white px-4 py-2 rounded-lg text-xs font-semibold shadow flex items-center gap-1.5 transition">
                        ⚡ Auto-Dispense Daily Feed (Biomass-Based)
                    </button>
                </form>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="bg-white p-5 rounded-xl shadow-sm border space-y-3">
                    <div class="flex justify-between items-center mb-1">
                        <h3 class="font-bold text-sm text-slate-700">Feed Stock Levels</h3>
                        <button onclick="document.getElementById('modalAddFeed').classList.remove('hidden')" class="bg-teal-600 text-white px-3 py-1.5 rounded-lg hover:bg-teal-700 text-xs font-semibold">
                            + Add Feed Item
                        </button>
                    </div>
                    <div class="space-y-3">
                        {% for f in feeds %}
                        <div class="searchable-card flex justify-between items-center p-3.5 rounded-lg border {% if f.stock_kg <= f.threshold_kg %}bg-amber-50 border-amber-200{% else %}bg-slate-50{% endif %}" data-search="{{ f.name }}">
                            <div>
                                <p class="font-bold text-sm text-slate-800">{{ f.name }}</p>
                                <p class="text-xs text-slate-500">Reorder Level: {{ f.threshold_kg }} kg</p>
                            </div>
                            <div class="text-right flex items-center gap-2">
                                <div>
                                    <span class="font-bold text-lg {% if f.stock_kg <= f.threshold_kg %}text-amber-700{% else %}text-slate-800{% endif %}">{{ f.stock_kg }} kg</span>
                                    <!-- [AFFMS_06_02] LOW STOCK ALERT BADGE -->
                                    {% if f.stock_kg <= f.threshold_kg %}
                                    <span class="block text-[10px] text-amber-600 font-bold">⚠️ LOW STOCK</span>
                                    {% endif %}
                                </div>
                                <button onclick="openEditFeedModal('{{ f.id }}', '{{ f.name }}', '{{ f.stock_kg }}', '{{ f.threshold_kg }}')" class="text-xs text-teal-700 hover:text-teal-900 px-2 py-1 bg-white border border-slate-300 rounded shadow-sm font-semibold">✏️ Edit</button>
                                <a href="/feed/delete/{{ f.id }}" onclick="return confirm('Delete this feed inventory item?')" class="text-xs text-rose-600 hover:text-rose-800 px-2 py-1 bg-white border border-slate-300 rounded shadow-sm font-semibold">Delete</a>
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>

                <!-- [AFFMS_06_03] BIOMASS FEEDING RATION CALCULATOR -->
                <div class="bg-white p-5 rounded-xl shadow-sm border space-y-4">
                    <h3 class="font-bold text-sm text-slate-700">Daily Feed Ration Calculator</h3>
                    <p class="text-xs text-slate-500">Calculates 3% body-weight feed requirement and splits across 3 daily meals.</p>
                    
                    <div class="space-y-3">
                        <div>
                            <label class="block text-xs font-semibold text-slate-600 mb-1">Select Batch</label>
                            <select id="calcBatchSelect" onchange="runCalc()" class="w-full border rounded-lg p-2 text-sm">
                                {% for b in batches %}
                                <option value="{{ b.biomass_kg }}">{{ b.pond_name }} - {{ b.species }} ({{ b.biomass_kg }} kg biomass)</option>
                                {% endfor %}
                            </select>
                        </div>
                        <div class="bg-teal-50 p-4 rounded-lg border border-teal-200 text-xs space-y-2">
                            <p class="font-bold text-teal-800 text-sm">Recommended Daily Feed: <span id="resTotal">0</span> kg</p>
                            <div class="grid grid-cols-3 gap-2 text-center pt-2 border-t border-teal-200">
                                <div class="bg-white p-2 rounded shadow-sm">
                                    <span class="block text-slate-400">Morning (40%)</span>
                                    <span id="resMorn" class="font-bold text-teal-700">0 kg</span>
                                </div>
                                <div class="bg-white p-2 rounded shadow-sm">
                                    <span class="block text-slate-400">Noon (30%)</span>
                                    <span id="resNoon" class="font-bold text-teal-700">0 kg</span>
                                </div>
                                <div class="bg-white p-2 rounded shadow-sm">
                                    <span class="block text-slate-400">Evening (30%)</span>
                                    <span id="resEve" class="font-bold text-teal-700">0 kg</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

        {% endif %}
    </main>

    <!-- REGISTER BATCH MODAL -->
    <div id="modalBatch" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg border max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-bold text-slate-800">Register New Fish Batch</h3>
            <form action="/batch/add" method="POST" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Pond Name</label>
                    <input type="text" name="pond_name" placeholder="Pond C" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Species</label>
                    <input type="text" name="species" placeholder="Tilapia / Catfish" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Stocking Count</label>
                        <input type="number" name="initial_count" placeholder="5000" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Avg Weight (g)</label>
                        <input type="number" step="0.1" name="avg_weight_grams" placeholder="100" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Stocking Date</label>
                    <input type="date" name="stocking_date" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div class="flex gap-2 justify-end pt-2">
                    <button type="button" onclick="document.getElementById('modalBatch').classList.add('hidden')" class="px-4 py-2 bg-slate-100 rounded-lg text-xs font-semibold">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold">Save Batch</button>
                </div>
            </form>
        </div>
    </div>

    <!-- EDIT BATCH MODAL -->
    <div id="modalEditBatch" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg border max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-bold text-slate-800">Edit Batch Details</h3>
            <form id="formEditBatch" method="POST" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Pond Name</label>
                    <input type="text" id="editPondName" name="pond_name" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Species</label>
                    <input type="text" id="editSpecies" name="species" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Initial Count</label>
                        <input type="number" id="editInitialCount" name="initial_count" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Current Count</label>
                        <input type="number" id="editCurrentCount" name="current_count" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Avg Weight (g)</label>
                        <input type="number" step="0.1" id="editAvgWeight" name="avg_weight_grams" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Stocking Date</label>
                        <input type="date" id="editStockingDate" name="stocking_date" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="flex gap-2 justify-end pt-2">
                    <button type="button" onclick="document.getElementById('modalEditBatch').classList.add('hidden')" class="px-4 py-2 bg-slate-100 rounded-lg text-xs font-semibold">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold">Update Batch</button>
                </div>
            </form>
        </div>
    </div>

    <!-- EDIT WATER LOG MODAL -->
    <div id="modalEditWater" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg border max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-bold text-slate-800">Edit Water Reading Log</h3>
            <form id="formEditWater" method="POST" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Target Pond</label>
                    <select id="editWaterPond" name="pond_name" class="w-full border rounded-lg p-2 text-sm" required>
                        {% for b in batches %}
                        <option value="{{ b.pond_name }}">{{ b.pond_name }} ({{ b.species }})</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">pH Level</label>
                        <input type="number" step="0.1" id="editWaterPh" name="ph" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Dissolved Oxygen (mg/L)</label>
                        <input type="number" step="0.1" id="editWaterDo" name="dissolved_oxygen" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Temp (°C)</label>
                        <input type="number" step="0.1" id="editWaterTemp" name="temp_celsius" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Ammonia (ppm)</label>
                        <input type="number" step="0.01" id="editWaterAmmonia" name="ammonia" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="flex gap-2 justify-end pt-2">
                    <button type="button" onclick="document.getElementById('modalEditWater').classList.add('hidden')" class="px-4 py-2 bg-slate-100 rounded-lg text-xs font-semibold">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold">Update Log</button>
                </div>
            </form>
        </div>
    </div>

    <!-- ADD FEED MODAL -->
    <div id="modalAddFeed" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg border max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-bold text-slate-800">Add New Feed Stock Item</h3>
            <form action="/feed/add" method="POST" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Feed Name / Description</label>
                    <input type="text" name="name" placeholder="Finisher Pellets (24% Protein)" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Initial Stock (kg)</label>
                        <input type="number" step="0.1" name="stock_kg" placeholder="200.0" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Reorder Level (kg)</label>
                        <input type="number" step="0.1" name="threshold_kg" placeholder="100.0" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="flex gap-2 justify-end pt-2">
                    <button type="button" onclick="document.getElementById('modalAddFeed').classList.add('hidden')" class="px-4 py-2 bg-slate-100 rounded-lg text-xs font-semibold">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold">Save Feed Item</button>
                </div>
            </form>
        </div>
    </div>

    <!-- EDIT FEED MODAL -->
    <div id="modalEditFeed" class="hidden fixed inset-0 bg-slate-900/50 backdrop-blur-sm flex justify-center items-center p-4 z-50">
        <div class="bg-white rounded-xl shadow-lg border max-w-md w-full p-6 space-y-4">
            <h3 class="text-lg font-bold text-slate-800">Edit Feed Stock</h3>
            <form id="formEditFeed" method="POST" class="space-y-3">
                <div>
                    <label class="block text-xs font-semibold text-slate-600 mb-1">Feed Name</label>
                    <input type="text" id="editFeedName" name="name" required class="w-full border rounded-lg p-2 text-sm">
                </div>
                <div class="grid grid-cols-2 gap-3">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Stock Level (kg)</label>
                        <input type="number" step="0.1" id="editStockKg" name="stock_kg" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Reorder Level (kg)</label>
                        <input type="number" step="0.1" id="editThresholdKg" name="threshold_kg" required class="w-full border rounded-lg p-2 text-sm">
                    </div>
                </div>
                <div class="flex gap-2 justify-end pt-2">
                    <button type="button" onclick="document.getElementById('modalEditFeed').classList.add('hidden')" class="px-4 py-2 bg-slate-100 rounded-lg text-xs font-semibold">Cancel</button>
                    <button type="submit" class="px-4 py-2 bg-teal-600 text-white rounded-lg text-xs font-semibold">Update Feed</button>
                </div>
            </form>
        </div>
    </div>

    <script>
        function showAuthBox(target) {
            document.getElementById('auth-login-box').classList.add('hidden');
            document.getElementById('auth-register-box').classList.add('hidden');
            document.getElementById('auth-reset-box').classList.add('hidden');
            document.getElementById('auth-' + target + '-box').classList.remove('hidden');
        }

        function switchTab(tabId) {
            ['overview', 'ponds', 'water', 'feed'].forEach(t => {
                const sec = document.getElementById('sec-' + t);
                const tab = document.getElementById('tab-' + t);
                if (sec) sec.classList.add('hidden');
                if (tab) {
                    tab.classList.remove('text-teal-600', 'border-teal-600');
                    tab.classList.add('border-transparent');
                }
            });
            const targetSec = document.getElementById('sec-' + tabId);
            const targetTab = document.getElementById('tab-' + tabId);
            if (targetSec) targetSec.classList.remove('hidden');
            if (targetTab) {
                targetTab.classList.add('text-teal-600', 'border-teal-600');
                targetTab.classList.remove('border-transparent');
            }
        }

        function filterAllData() {
            const query = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.searchable-card').forEach(card => {
                const text = card.getAttribute('data-search').toLowerCase();
                card.style.display = text.includes(query) ? '' : 'none';
            });
            document.querySelectorAll('.searchable-row').forEach(row => {
                const text = row.getAttribute('data-search').toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        }

        function openEditBatchModal(id, pond, species, initCount, currCount, avgWeight, date) {
            document.getElementById('formEditBatch').action = '/batch/update/' + id;
            document.getElementById('editPondName').value = pond;
            document.getElementById('editSpecies').value = species;
            document.getElementById('editInitialCount').value = initCount;
            document.getElementById('editCurrentCount').value = currCount;
            document.getElementById('editAvgWeight').value = avgWeight;
            document.getElementById('editStockingDate').value = date;
            document.getElementById('modalEditBatch').classList.remove('hidden');
        }

        function openEditWaterModal(id, pond, ph, doVal, temp, ammonia) {
            document.getElementById('formEditWater').action = '/water/update/' + id;
            document.getElementById('editWaterPond').value = pond;
            document.getElementById('editWaterPh').value = ph;
            document.getElementById('editWaterDo').value = doVal;
            document.getElementById('editWaterTemp').value = temp;
            document.getElementById('editWaterAmmonia').value = ammonia;
            document.getElementById('modalEditWater').classList.remove('hidden');
        }

        function openEditFeedModal(id, name, stock, threshold) {
            document.getElementById('formEditFeed').action = '/feed/update/' + id;
            document.getElementById('editFeedName').value = name;
            document.getElementById('editStockKg').value = stock;
            document.getElementById('editThresholdKg').value = threshold;
            document.getElementById('modalEditFeed').classList.remove('hidden');
        }

        function runCalc() {
            const select = document.getElementById('calcBatchSelect');
            if (!select) return;
            const biomass = parseFloat(select.value) || 0;
            const totalFeed = (biomass * 0.03).toFixed(2);
            document.getElementById('resTotal').innerText = totalFeed;
            document.getElementById('resMorn').innerText = (totalFeed * 0.40).toFixed(2) + " kg";
            document.getElementById('resNoon').innerText = (totalFeed * 0.30).toFixed(2) + " kg";
            document.getElementById('resEve').innerText = (totalFeed * 0.30).toFixed(2) + " kg";
        }

        {% if current_user %}
        window.onload = function() {
            runCalc();
            const ctxWater = document.getElementById('chartWaterTrends').getContext('2d');
            new Chart(ctxWater, {
                type: 'line',
                data: {
                    labels: [{% for l in water_logs %}'{{ l.timestamp }}',{% endfor %}],
                    datasets: [
                        { label: 'pH', data: [{% for l in water_logs %}{{ l.ph }},{% endfor %}], borderColor: '#0d9488', tension: 0.3 },
                        { label: 'Oxygen (mg/L)', data: [{% for l in water_logs %}{{ l.dissolved_oxygen }},{% endfor %}], borderColor: '#0284c7', tension: 0.3 }
                    ]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });

            const ctxSpecies = document.getElementById('chartSpecies').getContext('2d');
            new Chart(ctxSpecies, {
                type: 'doughnut',
                data: {
                    labels: [{% for b in batches %}'{{ b.species }}',{% endfor %}],
                    datasets: [{
                        data: [{% for b in batches %}{{ b.current_count }},{% endfor %}],
                        backgroundColor: ['#0d9488', '#0284c7', '#f59e0b', '#10b981']
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false }
            });
        };
        {% endif %}
    </script>
</body>
</html>
"""

# --- ROUTES & CONTROLLERS ---

@app.route('/')
def index():
    user_id = session.get('user_id')
    current_user = User.query.get(user_id) if user_id else None

    batches = PondBatch.query.all()
    water_logs = WaterLog.query.order_by(WaterLog.id.desc()).all()
    feeds = FeedInventory.query.all()

    total_fish = sum(b.current_count for b in batches)
    total_feed = sum(f.stock_kg for f in feeds)

    auth_error = session.pop('auth_error', None)
    auth_success = session.pop('auth_success', None)
    auth_view = session.pop('auth_view', 'register') # Default view set to register
    toast_msg = session.pop('toast_msg', None)

    return render_template_string(
        HTML_TEMPLATE,
        current_user=current_user,
        batches=batches,
        water_logs=water_logs,
        feeds=feeds,
        total_fish=total_fish,
        total_feed=total_feed,
        auth_error=auth_error,
        auth_success=auth_success,
        auth_view=auth_view,
        toast_msg=toast_msg
    )

# --- [AFFMS_01] REGISTER ADMIN ---
@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = "Farm Manager" # Automatically assigns Admin / Farm Manager role

    if len(password) < 6:
        session['auth_error'] = "Password must be at least 6 characters long."
        session['auth_view'] = "register"
    elif User.query.filter_by(email=email).first():
        session['auth_error'] = "Email address is already registered. Please sign in instead."
        session['auth_view'] = "register"
    else:
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password_hash=hashed_password, role=role)
        db.session.add(new_user)
        db.session.commit()
        session['auth_success'] = "Admin account created successfully! You can now sign in."
        session['auth_view'] = "login"

    return redirect(url_for('index'))

# --- [AFFMS_02] LOGIN USER ---
@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        session['toast_msg'] = f"Welcome back, {user.name}!"
    else:
        session['auth_error'] = "Invalid email or password credentials."
        session['auth_view'] = "login"
    
    return redirect(url_for('index'))

# --- [AFFMS_03] RESET PASSWORD & LOGOUT ---
@app.route('/reset-password', methods=['POST'])
def reset_password():
    email = request.form.get('email', '').strip()
    new_password = request.form.get('new_password', '').strip()
    confirm_password = request.form.get('confirm_password', '').strip()

    if new_password != confirm_password:
        session['auth_error'] = "New passwords do not match. Please try again."
        session['auth_view'] = "reset"
        return redirect(url_for('index'))

    user = User.query.filter_by(email=email).first()
    if not user:
        session['auth_error'] = "No account found with that email address."
        session['auth_view'] = "reset"
    else:
        user.password_hash = generate_password_hash(new_password)
        db.session.commit()
        session['auth_success'] = "Password updated successfully! Please sign in with your new password."
        session['auth_view'] = "login"

    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

# --- [AFFMS_04] BATCH MANAGEMENT ROUTES ---
@app.route('/batch/add', methods=['POST'])
def add_batch():
    if 'user_id' not in session: return redirect(url_for('index'))
    
    pond_name = request.form['pond_name']
    species = request.form['species']
    initial_count = int(request.form['initial_count'])
    avg_weight_grams = float(request.form['avg_weight_grams'])
    stocking_date = request.form['stocking_date']

    new_batch = PondBatch(
        pond_name=pond_name,
        species=species,
        initial_count=initial_count,
        current_count=initial_count,
        avg_weight_grams=avg_weight_grams,
        stocking_date=stocking_date
    )
    db.session.add(new_batch)
    db.session.commit()
    session['toast_msg'] = f"New batch '{pond_name}' registered successfully!"
    return redirect(url_for('index'))

@app.route('/batch/update/<int:batch_id>', methods=['POST'])
def update_batch(batch_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    batch = PondBatch.query.get(batch_id)
    if batch:
        batch.pond_name = request.form['pond_name']
        batch.species = request.form['species']
        batch.initial_count = int(request.form['initial_count'])
        batch.current_count = int(request.form['current_count'])
        batch.avg_weight_grams = float(request.form['avg_weight_grams'])
        batch.stocking_date = request.form['stocking_date']
        db.session.commit()
        session['toast_msg'] = f"Batch '{batch.pond_name}' updated successfully!"
    return redirect(url_for('index'))

@app.route('/batch/delete/<int:batch_id>')
def delete_batch(batch_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    batch = PondBatch.query.get(batch_id)
    if batch:
        pond_name = batch.pond_name
        db.session.delete(batch)
        db.session.commit()
        session['toast_msg'] = f"Batch '{pond_name}' deleted."
    return redirect(url_for('index'))

# --- [AFFMS_05] WATER QUALITY & AUTOMATED SENSOR SCAN ROUTES ---
@app.route('/water/add', methods=['POST'])
def add_water_log():
    if 'user_id' not in session: return redirect(url_for('index'))

    pond_name = request.form['pond_name']
    ph = float(request.form['ph'])
    dissolved_oxygen = float(request.form['dissolved_oxygen'])
    temp_celsius = float(request.form['temp_celsius'])
    ammonia = float(request.form['ammonia'])

    status = "Safe"
    if (ph < 6.5 or ph > 8.5 or 
        dissolved_oxygen < 5.0 or 
        temp_celsius < 25.0 or temp_celsius > 32.0 or 
        ammonia > 0.05):
        status = "Alert"

    time_str = datetime.now().strftime("%I:%M %p")
    new_log = WaterLog(
        timestamp=time_str,
        pond_name=pond_name,
        ph=ph,
        dissolved_oxygen=dissolved_oxygen,
        temp_celsius=temp_celsius,
        ammonia=ammonia,
        status=status
    )
    db.session.add(new_log)
    db.session.commit()

    if status == "Alert":
        session['toast_msg'] = f"⚠️ WARNING: Suboptimal water parameters logged for {pond_name}!"
    else:
        session['toast_msg'] = f"Water telemetry logged for {pond_name} (Optimal)."

    return redirect(url_for('index'))

@app.route('/water/auto-scan', methods=['POST'])
def auto_scan_water():
    if 'user_id' not in session: return redirect(url_for('index'))

    batches = PondBatch.query.all()
    if not batches:
        session['toast_msg'] = "No active ponds found to run automated scan."
        return redirect(url_for('index'))

    time_str = datetime.now().strftime("%I:%M %p")
    alert_count = 0

    for b in batches:
        ph = round(random.uniform(6.3, 8.4), 1)
        dissolved_oxygen = round(random.uniform(4.7, 7.2), 1)
        temp_celsius = round(random.uniform(25.5, 31.8), 1)
        ammonia = round(random.uniform(0.01, 0.06), 2)

        status = "Safe"
        if (ph < 6.5 or ph > 8.5 or 
            dissolved_oxygen < 5.0 or 
            temp_celsius < 25.0 or temp_celsius > 32.0 or 
            ammonia > 0.05):
            status = "Alert"
            alert_count += 1

        new_log = WaterLog(
            timestamp=time_str,
            pond_name=b.pond_name,
            ph=ph,
            dissolved_oxygen=dissolved_oxygen,
            temp_celsius=temp_celsius,
            ammonia=ammonia,
            status=status
        )
        db.session.add(new_log)

    db.session.commit()

    if alert_count > 0:
        session['toast_msg'] = f"🤖 WARNING: Automated IoT telemetry scan logged for {len(batches)} ponds ({alert_count} alert(s) detected)!"
    else:
        session['toast_msg'] = f"🤖 Automated IoT telemetry scan completed for {len(batches)} ponds (All Optimal)."

    return redirect(url_for('index'))

@app.route('/water/update/<int:log_id>', methods=['POST'])
def update_water_log(log_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    log = WaterLog.query.get(log_id)
    if log:
        log.pond_name = request.form['pond_name']
        log.ph = float(request.form['ph'])
        log.dissolved_oxygen = float(request.form['dissolved_oxygen'])
        log.temp_celsius = float(request.form['temp_celsius'])
        log.ammonia = float(request.form['ammonia'])

        status = "Safe"
        if (log.ph < 6.5 or log.ph > 8.5 or 
            log.dissolved_oxygen < 5.0 or 
            log.temp_celsius < 25.0 or log.temp_celsius > 32.0 or 
            log.ammonia > 0.05):
            status = "Alert"
        log.status = status

        db.session.commit()
        if status == "Alert":
            session['toast_msg'] = f"⚠️ WARNING: Suboptimal water parameters updated for {log.pond_name}!"
        else:
            session['toast_msg'] = f"Water reading for {log.pond_name} updated successfully!"
    return redirect(url_for('index'))

@app.route('/water/delete/<int:log_id>')
def delete_water_log(log_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    log = WaterLog.query.get(log_id)
    if log:
        pond_name = log.pond_name
        db.session.delete(log)
        db.session.commit()
        session['toast_msg'] = f"Water quality log for {pond_name} deleted."
    return redirect(url_for('index'))

# --- [AFFMS_06] FEED INVENTORY & AUTOMATED DISPENSER ROUTES ---
@app.route('/feed/add', methods=['POST'])
def add_feed():
    if 'user_id' not in session: return redirect(url_for('index'))
    name = request.form['name']
    stock_kg = float(request.form['stock_kg'])
    threshold_kg = float(request.form['threshold_kg'])

    new_feed = FeedInventory(name=name, stock_kg=stock_kg, threshold_kg=threshold_kg)
    db.session.add(new_feed)
    db.session.commit()
    session['toast_msg'] = f"New feed item '{name}' added to inventory!"
    return redirect(url_for('index'))

@app.route('/feed/auto-dispense', methods=['POST'])
def auto_dispense_feed():
    if 'user_id' not in session: return redirect(url_for('index'))

    batches = PondBatch.query.all()
    feeds = FeedInventory.query.all()

    if not batches or not feeds:
        session['toast_msg'] = "Automation halted: Ensure active ponds and feed items exist."
        return redirect(url_for('index'))

    # Calculate total daily feed needed (3% of total pond biomass)
    total_biomass = sum(b.biomass_kg for b in batches)
    daily_feed_needed = round(total_biomass * 0.03, 1)

    if daily_feed_needed <= 0:
        session['toast_msg'] = "No feed deduction required for current biomass."
        return redirect(url_for('index'))

    # Deduct from primary feed stock
    primary_feed = feeds[0]
    primary_feed.stock_kg = max(0.0, round(primary_feed.stock_kg - daily_feed_needed, 1))
    db.session.commit()

    if primary_feed.stock_kg <= primary_feed.threshold_kg:
        session['toast_msg'] = f"⚡ Auto-Dispensed {daily_feed_needed} kg. ⚠️ LOW STOCK WARNING on '{primary_feed.name}'!"
    else:
        session['toast_msg'] = f"⚡ Automated Feed Dispenser: Deducted {daily_feed_needed} kg daily feed based on pond biomass!"

    return redirect(url_for('index'))

@app.route('/feed/update/<int:feed_id>', methods=['POST'])
def update_feed(feed_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    feed = FeedInventory.query.get(feed_id)
    if feed:
        feed.name = request.form['name']
        feed.stock_kg = float(request.form['stock_kg'])
        feed.threshold_kg = float(request.form['threshold_kg'])
        db.session.commit()
        session['toast_msg'] = f"Feed stock for '{feed.name}' updated!"
    return redirect(url_for('index'))

@app.route('/feed/delete/<int:feed_id>')
def delete_feed(feed_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    feed = FeedInventory.query.get(feed_id)
    if feed:
        feed_name = feed.name
        db.session.delete(feed)
        db.session.commit()
        session['toast_msg'] = f"Feed item '{feed_name}' deleted from inventory."
    return redirect(url_for('index'))

# --- AUTOMATIC DATABASE INITIALIZATION ---
with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        # Seed Demo Users
        db.session.add(User(name="Kok Jie", email="admin@affms.com", password_hash=generate_password_hash("admin123"), role="Farm Manager"))
        db.session.add(User(name="Ahmad", email="worker@affms.com", password_hash=generate_password_hash("worker123"), role="Field Technician"))
        
        # Seed Demo Batches
        db.session.add(PondBatch(pond_name="Pond A", species="Tilapia", initial_count=5000, current_count=4850, avg_weight_grams=250.0, stocking_date="2026-01-15"))
        db.session.add(PondBatch(pond_name="Pond B", species="Catfish", initial_count=8000, current_count=7600, avg_weight_grams=180.0, stocking_date="2026-02-01"))

        # Seed Water Logs
        db.session.add(WaterLog(timestamp="10:00 AM", pond_name="Pond A", ph=7.2, dissolved_oxygen=6.5, temp_celsius=27.5, ammonia=0.02, status="Safe"))
        db.session.add(WaterLog(timestamp="10:15 AM", pond_name="Pond B", ph=6.1, dissolved_oxygen=5.8, temp_celsius=28.0, ammonia=0.04, status="Alert"))

        # Seed Feed Inventory
        db.session.add(FeedInventory(name="High-Protein Starter Pellets (32%)", stock_kg=120.0, threshold_kg=150.0))
        db.session.add(FeedInventory(name="Grower Pellets (28%)", stock_kg=450.0, threshold_kg=200.0))

        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
