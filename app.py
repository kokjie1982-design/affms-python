import os
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# --- APP CONFIGURATION ---
app = Flask(__name__)
app.secret_key = "affms_secret_key_change_in_production"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///affms.db'
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
    <title>AFFMS - Python Flask Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body class="bg-slate-100 text-slate-800 font-sans min-h-screen flex flex-col">

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
                <p class="text-[11px] text-teal-200 mt-0.5">Python Flask & SQLite Web System</p>
            </div>
        </div>

        {% if current_user %}
        <div class="flex items-center gap-3">
            <div class="text-right text-xs">
                <p class="font-bold text-white">{{ current_user.name }}</p>
                <p class="text-teal-200 text-[10px]">{{ current_user.role }}</p>
            </div>
            <a href="/logout" class="bg-teal-800 hover:bg-teal-900 text-teal-100 text-xs px-3 py-1.5 rounded border border-teal-600 transition">
                Logout
            </a>
        </div>
        {% endif %}
    </header>

    {% if current_user %}
    <!-- NAVIGATION TABS -->
    <nav class="bg-white border-b flex justify-center md:justify-start gap-6 px-6 py-3 font-semibold text-sm text-slate-600 shadow-sm">
        <button onclick="switchTab('overview')" id="tab-overview" class="hover:text-teal-600 pb-1 border-b-2 border-teal-600 text-teal-600 transition">Overview Dashboard</button>
        <button onclick="switchTab('ponds')" id="tab-ponds" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Ponds & Batches</button>
        <button onclick="switchTab('water')" id="tab-water" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Water Quality</button>
        <button onclick="switchTab('feed')" id="tab-feed" class="hover:text-teal-600 pb-1 border-b-2 border-transparent transition">Feed & Inventory</button>
    </nav>
    {% endif %}

    <!-- MAIN CONTAINER -->
    <main class="p-4 md:p-6 max-w-7xl mx-auto w-full flex-grow">

        {% if not current_user %}
        <!-- LOGIN MODULE -->
        <section class="flex justify-center items-center py-8">
            <div class="bg-white p-8 rounded-xl shadow-md border border-slate-200 max-w-md w-full space-y-6">
                <div class="text-center space-y-2">
                    <h2 class="text-2xl font-bold text-slate-800">AFFMS Portal Sign In</h2>
                    <p class="text-xs text-slate-500">Sign in to access farm telemetry and batch management</p>
                </div>

                {% if login_error %}
                <div class="bg-rose-50 border border-rose-200 text-rose-700 text-xs p-3 rounded-lg font-medium">
                    {{ login_error }}
                </div>
                {% endif %}

                <form action="/login" method="POST" class="space-y-4">
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Email Address</label>
                        <input type="email" name="email" value="admin@affms.com" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Password</label>
                        <input type="password" name="password" value="admin123" required class="w-full border border-slate-300 rounded-lg p-2.5 text-sm focus:ring-2 focus:ring-teal-500">
                    </div>
                    <button type="submit" class="w-full bg-teal-700 hover:bg-teal-800 text-white font-semibold py-2.5 rounded-lg text-sm shadow transition">
                        Sign In
                    </button>
                </form>

                <div class="border-t pt-4 text-xs text-slate-500 space-y-2">
                    <p class="font-semibold text-slate-700">Demo Accounts:</p>
                    <p>• <strong>Manager:</strong> admin@affms.com / admin123</p>
                    <p>• <strong>Technician:</strong> worker@affms.com / worker123</p>
                </div>
            </div>
        </section>
        {% else %}

        <!-- 1. OVERVIEW DASHBOARD -->
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

        <!-- 2. PONDS & FISH BATCH LIFECYCLE -->
        <section id="sec-ponds" class="hidden space-y-6">
            <div class="flex justify-between items-center">
                <h2 class="text-xl font-bold text-slate-800">Pond & Fish Batch Lifecycle</h2>
                <button onclick="document.getElementById('modalBatch').classList.remove('hidden')" class="bg-teal-600 text-white px-4 py-2 rounded-lg hover:bg-teal-700 text-sm font-semibold">
                    + Register New Batch
                </button>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                {% for b in batches %}
                <div class="bg-white p-5 rounded-xl shadow-sm border space-y-3">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="text-lg font-bold text-slate-800">{{ b.pond_name }} ({{ b.species }})</h3>
                            <p class="text-xs text-slate-500">Stocked: {{ b.stocking_date }}</p>
                        </div>
                        <span class="bg-emerald-100 text-emerald-800 text-xs px-2.5 py-1 rounded-full font-semibold">{{ b.case_survival_rate }}% Survival</span>
                    </div>
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
                        <a href="/batch/delete/{{ b.id }}" onclick="return confirm('Delete this batch?')" class="text-xs text-rose-600 hover:text-rose-800 px-3 py-1 rounded bg-rose-50">Delete</a>
                    </div>
                </div>
                {% endfor %}
            </div>
        </section>

        <!-- 3. WATER QUALITY MONITORING -->
        <section id="sec-water" class="hidden space-y-6">
            <h2 class="text-xl font-bold text-slate-800">Water Quality Telemetry & Thresholds</h2>

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
                        <label class="block text-xs font-semibold text-slate-600 mb-1">pH Level (6.5 - 8.5)</label>
                        <input type="number" step="0.1" name="ph" value="7.2" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Dissolved Oxygen (mg/L)</label>
                        <input type="number" step="0.1" name="dissolved_oxygen" value="6.5" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Temp (°C)</label>
                        <input type="number" step="0.1" name="temp_celsius" value="27.5" class="w-full border rounded-lg p-2 text-sm" required>
                    </div>
                    <div>
                        <label class="block text-xs font-semibold text-slate-600 mb-1">Ammonia (ppm)</label>
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
                                <th class="p-3">Temp</th>
                                <th class="p-3">Ammonia</th>
                                <th class="p-3">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for l in water_logs %}
                            <tr class="border-b hover:bg-slate-50">
                                <td class="p-3 font-medium">{{ l.timestamp }}</td>
                                <td class="p-3">{{ l.pond_name }}</td>
                                <td class="p-3 {% if l.ph < 6.5 or l.ph > 8.5 %}text-amber-600 font-bold{% endif %}">{{ l.ph }}</td>
                                <td class="p-3 {% if l.dissolved_oxygen < 5.0 %}text-amber-600 font-bold{% endif %}">{{ l.dissolved_oxygen }}</td>
                                <td class="p-3">{{ l.temp_celsius }}°C</td>
                                <td class="p-3">{{ l.ammonia }}</td>
                                <td class="p-3">
                                    <span class="px-2 py-0.5 rounded text-xs font-semibold {% if l.status == 'Safe' %}bg-emerald-100 text-emerald-800{% else %}bg-amber-100 text-amber-800{% endif %}">
                                        {{ l.status }}
                                    </span>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </section>

        <!-- 4. FEED INVENTORY & CALCULATOR -->
        <section id="sec-feed" class="hidden space-y-6">
            <h2 class="text-xl font-bold text-slate-800">Feed Inventory & Biomass Feeding Engine</h2>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div class="bg-white p-5 rounded-xl shadow-sm border space-y-3">
                    <h3 class="font-bold text-sm text-slate-700">Feed Stock Levels</h3>
                    <div class="space-y-3">
                        {% for f in feeds %}
                        <div class="flex justify-between items-center p-3 rounded-lg border {% if f.stock_kg <= f.threshold_kg %}bg-amber-50 border-amber-200{% else %}bg-slate-50{% endif %}">
                            <div>
                                <p class="font-bold text-sm text-slate-800">{{ f.name }}</p>
                                <p class="text-xs text-slate-500">Reorder Level: {{ f.threshold_kg }} kg</p>
                            </div>
                            <div class="text-right">
                                <span class="font-bold text-lg {% if f.stock_kg <= f.threshold_kg %}text-amber-700{% else %}text-slate-800{% endif %}">{{ f.stock_kg }} kg</span>
                                {% if f.stock_kg <= f.threshold_kg %}
                                <span class="block text-[10px] text-amber-600 font-bold">⚠️ LOW STOCK</span>
                                {% endif %}
                            </div>
                        </div>
                        {% endfor %}
                    </div>
                </div>

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

    <script>
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

    return render_template_string(
        HTML_TEMPLATE,
        current_user=current_user,
        batches=batches,
        water_logs=water_logs,
        feeds=feeds,
        total_fish=total_fish,
        total_feed=total_feed,
        login_error=session.pop('login_error', None)
    )

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()

    user = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
    else:
        session['login_error'] = "Invalid email or password."
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

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
    return redirect(url_for('index'))

@app.route('/batch/delete/<int:batch_id>')
def delete_batch(batch_id):
    if 'user_id' not in session: return redirect(url_for('index'))
    batch = PondBatch.query.get(batch_id)
    if batch:
        db.session.delete(batch)
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/water/add', methods=['POST'])
def add_water_log():
    if 'user_id' not in session: return redirect(url_for('index'))

    pond_name = request.form['pond_name']
    ph = float(request.form['ph'])
    dissolved_oxygen = float(request.form['dissolved_oxygen'])
    temp_celsius = float(request.form['temp_celsius'])
    ammonia = float(request.form['ammonia'])

    status = "Safe"
    if ph < 6.5 or ph > 8.5 or dissolved_oxygen < 5.0 or ammonia > 0.05:
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
    return redirect(url_for('index'))

# --- AUTOMATIC DATABASE INITIALIZATION FOR RENDER / GUNICORN ---
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
