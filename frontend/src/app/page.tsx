'use client';

import { useState, useEffect } from 'react';
import PlotComponent from '@/components/Plot';

// Use direct API URL if provided (bypasses Vercel proxy limits/timeouts), otherwise fallback to proxy
const API_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

export default function Home() {
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [filters, setFilters] = useState<{ar_person: string[], sales_person_code: string[], name: string[]}>({
    ar_person: [], sales_person_code: [], name: []
  });
  const [metrics, setMetrics] = useState<any>(null);
  const [trends, setTrends] = useState<any[]>([]);
  const [tableData, setTableData] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'trend' | 'detail'>('trend');
  const [uploading, setUploading] = useState(false);
  
  // Filter Modal State
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [filterOptions, setFilterOptions] = useState<{ar_person: string[], sales_person_code: string[], name: string[]}>({
    ar_person: [], sales_person_code: [], name: []
  });

  useEffect(() => {
    fetch(`${API_URL}/snapshot`)
      .then(r => r.json())
      .then(data => setSnapshotId(data.snapshot_id))
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (snapshotId) {
      loadDashboard();
    }
  }, [snapshotId, filters]);

  const loadDashboard = async () => {
    const payload = { snapshot_id: snapshotId, filters };
    
    // Fetch Metrics
    fetch(`${API_URL}/metrics`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(setMetrics).catch(console.error);

    // Fetch Trends
    fetch(`${API_URL}/trend`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(setTrends).catch(console.error);

    // Fetch Table
    fetch(`${API_URL}/data`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(setTableData).catch(console.error);

    // Fetch Filter Options
    fetch(`${API_URL}/filters`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    }).then(r => r.json()).then(setFilterOptions).catch(console.error);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return;
    setUploading(true);
    const formData = new FormData();
    for (let i = 0; i < e.target.files.length; i++) {
      formData.append('files', e.target.files[i]);
    }
    
    try {
      const res = await fetch(`${API_URL}/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await res.json();
      if (data.success) {
        alert(`Successfully imported ${data.success_count} file(s)`);
        window.location.reload();
      } else {
        alert("Upload failed");
      }
    } catch (err) {
      console.error(err);
      alert("Error uploading files");
    } finally {
      setUploading(false);
    }
  };

  const formatMoney = (val: number) => {
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
    return `$${val.toLocaleString()}`;
  };

  const toggleFilter = (category: 'ar_person' | 'sales_person_code' | 'name', value: string, isChecked: boolean) => {
    setFilters(prev => {
      let current = prev[category];
      if (current.length === 1 && current[0] === '__NONE__') {
        current = [];
      }

      if (isChecked) {
        let updated = current.length === 0 ? [value] : [...current, value];
        if (updated.length === filterOptions[category].length) {
          return { ...prev, [category]: [] };
        }
        return { ...prev, [category]: updated };
      } else {
        if (current.length === 0) {
          const explicitList = filterOptions[category].filter(v => v !== value);
          if (explicitList.length === 0) return { ...prev, [category]: ['__NONE__'] };
          return { ...prev, [category]: explicitList };
        } else {
          const updated = current.filter(v => v !== value);
          if (updated.length === 0) return { ...prev, [category]: ['__NONE__'] };
          return { ...prev, [category]: updated };
        }
      }
    });
  };

  const toggleAll = (category: 'ar_person' | 'sales_person_code' | 'name', isChecked: boolean) => {
    setFilters(prev => ({
      ...prev,
      [category]: isChecked ? [] : ['__NONE__']
    }));
  };

  return (
    <>
    <main className="glass-container m-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-4xl font-extrabold bg-gradient-to-br from-slate-900 to-blue-500 bg-clip-text text-transparent">
            AR Intelligence Nexus
          </h1>
          <p className="text-slate-500 font-medium mt-1">
            Executive Accounts Receivable Command Center
          </p>
        </div>
        <div className="flex gap-4">
          <button className="btn-secondary" onClick={() => setShowFilterModal(true)}>
            Data Filters
          </button>
          <label className="btn-secondary cursor-pointer">
            {uploading ? "Importing..." : "Import Data"}
            <input type="file" multiple accept=".csv,.xlsx" className="hidden" onChange={handleFileUpload} disabled={uploading} />
          </label>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-6 mb-8">
        <div className="metric-card">
          <div className="metric-label">Total AR Amount</div>
          <div className="metric-value">{metrics ? formatMoney(metrics.total_ar) : '-'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Balance Overdue</div>
          <div className="metric-value">{metrics ? formatMoney(metrics.balance_overdue) : '-'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">% Overdue</div>
          <div className="metric-value">{metrics ? `${(metrics.pct_overdue * 100).toFixed(1)}%` : '-'}</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Total Customers</div>
          <div className="metric-value">{metrics ? metrics.total_customers.toLocaleString() : '-'}</div>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs-container mb-6">
        <button 
          className={`tab-btn ${activeTab === 'trend' ? 'active' : ''}`}
          onClick={() => setActiveTab('trend')}
        >
          Trend Analysis
        </button>
        <button 
          className={`tab-btn ${activeTab === 'detail' ? 'active' : ''}`}
          onClick={() => setActiveTab('detail')}
        >
          Detail Data
        </button>
      </div>

      {/* Content */}
      {activeTab === 'trend' && (
        <div>
          {trends.length === 0 ? (
            <p className="text-slate-500">No trend data available. Import data to view trends.</p>
          ) : (
            <div className="grid grid-cols-2 gap-6">
              {trends.map((chart, idx) => (
                <div key={idx} className="chart-container" style={{ height: '450px' }}>
                  <PlotComponent 
                    data={chart.fig_json.data} 
                    layout={chart.fig_json.layout}
                    config={{ displayModeBar: false }}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'detail' && (
        <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm">
          {tableData.length === 0 ? (
            <div className="p-12 text-center flex flex-col items-center justify-center">
              <div className="w-16 h-16 mb-4 rounded-full bg-slate-50 flex items-center justify-center">
                <span className="text-2xl opacity-50">📂</span>
              </div>
              <p className="text-slate-500 font-medium">No detail data available.</p>
              <p className="text-slate-400 text-sm mt-1">Try clearing your filters or importing new data.</p>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[600px]">
              <table className="w-full text-left text-sm text-slate-600">
                <thead className="bg-slate-50 text-slate-900 sticky top-0 shadow-sm z-10">
                  <tr>
                    {Object.keys(tableData[0]).map(k => (
                      <th key={k} className="p-4 font-semibold whitespace-nowrap">{k}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {tableData.map((row, i) => (
                    <tr key={i} className="hover:bg-slate-50 transition-colors">
                      {Object.values(row).map((val: any, j) => (
                        <td key={j} className="p-4 whitespace-nowrap">{val}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </main>
    
    {/* Filter Modal - Moved outside main to prevent CSS backdrop-filter containing block bug */}
    {showFilterModal && (
      <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm">
        <div className="bg-white rounded-3xl shadow-2xl p-8 w-[900px] max-w-[95vw] h-[80vh] flex flex-col border border-slate-100">
          <div className="flex justify-between items-center mb-6 shrink-0">
            <h2 className="text-2xl font-bold text-slate-800">Data Filters</h2>
            <button 
              onClick={() => setShowFilterModal(false)}
              className="text-slate-400 hover:text-slate-600 p-2 rounded-full hover:bg-slate-100 transition-colors"
            >
              ✕
            </button>
          </div>
          
          <div className="flex-1 min-h-0 grid grid-cols-3 gap-6">
            {/* AR Person */}
            <div className="flex flex-col min-h-0 bg-slate-50/50 rounded-xl border border-slate-100">
              <h3 className="font-semibold text-slate-700 bg-slate-100/80 p-3 rounded-t-xl text-center shrink-0 border-b border-slate-200">AR Person</h3>
              <div className="flex-1 overflow-y-auto flex flex-col gap-1 p-3">
                {filterOptions.ar_person.length > 0 && (
                  <label className="flex items-center gap-3 p-2 hover:bg-slate-100 rounded-lg cursor-pointer transition-colors border-b border-slate-200 bg-white w-full mb-1 shadow-sm">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-400 cursor-pointer"
                      checked={filters.ar_person.length === 0}
                      onChange={(e) => toggleAll('ar_person', e.target.checked)}
                    />
                    <span className="text-slate-800 font-bold text-sm truncate min-w-0 flex-1">ALL</span>
                  </label>
                )}
                {filterOptions.ar_person.map(opt => (
                  <label key={opt} className="flex items-center gap-3 p-2 hover:bg-white rounded-lg cursor-pointer transition-colors border border-transparent hover:border-blue-100 hover:shadow-sm w-full">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-300 cursor-pointer"
                      checked={filters.ar_person.length === 0 || (filters.ar_person.length > 0 && filters.ar_person[0] !== '__NONE__' && filters.ar_person.includes(opt))}
                      onChange={(e) => toggleFilter('ar_person', opt, e.target.checked)}
                    />
                    <span className="text-slate-600 text-sm truncate min-w-0 flex-1" title={opt}>{opt}</span>
                  </label>
                ))}
                {filterOptions.ar_person.length === 0 && <span className="text-slate-400 text-sm italic text-center py-4">No data</span>}
              </div>
            </div>

            {/* Sales Person */}
            <div className="flex flex-col min-h-0 bg-slate-50/50 rounded-xl border border-slate-100">
              <h3 className="font-semibold text-slate-700 bg-slate-100/80 p-3 rounded-t-xl text-center shrink-0 border-b border-slate-200">Sales Person</h3>
              <div className="flex-1 overflow-y-auto flex flex-col gap-1 p-3">
                {filterOptions.sales_person_code.length > 0 && (
                  <label className="flex items-center gap-3 p-2 hover:bg-slate-100 rounded-lg cursor-pointer transition-colors border-b border-slate-200 bg-white w-full mb-1 shadow-sm">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-400 cursor-pointer"
                      checked={filters.sales_person_code.length === 0}
                      onChange={(e) => toggleAll('sales_person_code', e.target.checked)}
                    />
                    <span className="text-slate-800 font-bold text-sm truncate min-w-0 flex-1">ALL</span>
                  </label>
                )}
                {filterOptions.sales_person_code.map(opt => (
                  <label key={opt} className="flex items-center gap-3 p-2 hover:bg-white rounded-lg cursor-pointer transition-colors border border-transparent hover:border-blue-100 hover:shadow-sm w-full">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-300 cursor-pointer"
                      checked={filters.sales_person_code.length === 0 || (filters.sales_person_code.length > 0 && filters.sales_person_code[0] !== '__NONE__' && filters.sales_person_code.includes(opt))}
                      onChange={(e) => toggleFilter('sales_person_code', opt, e.target.checked)}
                    />
                    <span className="text-slate-600 text-sm truncate min-w-0 flex-1" title={opt}>{opt}</span>
                  </label>
                ))}
                {filterOptions.sales_person_code.length === 0 && <span className="text-slate-400 text-sm italic text-center py-4">No data</span>}
              </div>
            </div>

            {/* Customer */}
            <div className="flex flex-col min-h-0 bg-slate-50/50 rounded-xl border border-slate-100">
              <h3 className="font-semibold text-slate-700 bg-slate-100/80 p-3 rounded-t-xl text-center shrink-0 border-b border-slate-200">Customer</h3>
              <div className="flex-1 overflow-y-auto flex flex-col gap-1 p-3">
                {filterOptions.name.length > 0 && (
                  <label className="flex items-center gap-3 p-2 hover:bg-slate-100 rounded-lg cursor-pointer transition-colors border-b border-slate-200 bg-white w-full mb-1 shadow-sm">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-400 cursor-pointer"
                      checked={filters.name.length === 0}
                      onChange={(e) => toggleAll('name', e.target.checked)}
                    />
                    <span className="text-slate-800 font-bold text-sm truncate min-w-0 flex-1">ALL</span>
                  </label>
                )}
                {filterOptions.name.map(opt => (
                  <label key={opt} className="flex items-center gap-3 p-2 hover:bg-white rounded-lg cursor-pointer transition-colors border border-transparent hover:border-blue-100 hover:shadow-sm w-full">
                    <input 
                      type="checkbox" 
                      className="shrink-0 w-5 h-5 rounded text-blue-600 focus:ring-blue-500 border-slate-300 cursor-pointer"
                      checked={filters.name.length === 0 || (filters.name.length > 0 && filters.name[0] !== '__NONE__' && filters.name.includes(opt))}
                      onChange={(e) => toggleFilter('name', opt, e.target.checked)}
                    />
                    <span className="text-slate-600 text-sm truncate min-w-0 flex-1" title={opt}>{opt}</span>
                  </label>
                ))}
                {filterOptions.name.length === 0 && <span className="text-slate-400 text-sm italic text-center py-4">No data</span>}
              </div>
            </div>
          </div>

          <div className="mt-8 shrink-0 flex justify-end gap-4 pt-4 border-t border-slate-100">
            <button 
              className="btn-secondary"
              onClick={() => setFilters({ ar_person: [], sales_person_code: [], name: [] })}
            >
              Clear All Filters
            </button>
            <button 
              className="btn-primary"
              onClick={() => setShowFilterModal(false)}
            >
              Apply & Close
            </button>
          </div>
        </div>
      </div>
    )}
    </>
  );
}
