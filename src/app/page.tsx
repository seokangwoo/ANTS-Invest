'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef } from 'ag-grid-community';
import Chart from '@/components/Chart';
import dynamic from 'next/dynamic';

import { getPath } from '@/utils/path';

import ConsensusTable from '@/components/ConsensusTable';

// Dynamic import for Chart to avoid SSR issues with canvas
const DynamicChart = dynamic(() => import('@/components/Chart'), { ssr: false });

interface TickerData {
    ticker: string;
    name: string;
    industry: string;
    marketcap: number;
    per: number;
    pbr: number;
    psr: number;
    ev_ebitda: number;
    perz: number;
    pbrz: number;
    psrz: number;
    ev_ebitda_z: number;
    pricez: number;
    sales_growth: number;
    op_growth: number;
    np_growth: number;
    // US specific
    pcr?: number;
    por?: number;
    yield?: number;
    // Consensus
    target_price?: number;
    upside?: number;
    current_price?: number;
}

export default function Home() {
    const [region, setRegion] = useState<'KR' | 'US'>('KR');
    const [rowData, setRowData] = useState<TickerData[]>([]);
    const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
    const [selectedColumn, setSelectedColumn] = useState<string>('pricez');

    useEffect(() => {
        // Fetch tickers based on region
        const path = region === 'KR' ? getPath('data/tickers.json') : getPath('data/us/tickers.json');
        fetch(path)
            .then((result) => result.json())
            .then((rowData) => {
                setRowData(rowData);
                setSelectedTicker(null); // Reset selection on region switch
                setSelectedColumn('pricez');
            })
            .catch((err) => {
                console.error("Failed to fetch tickers:", err);
                setRowData([]);
            });
    }, [region]);

    const colDefs: ColDef[] = useMemo(() => {
        const common: ColDef[] = [
            {
                field: 'ticker', headerName: 'Ticker', width: 90, pinned: 'left', cellRenderer: (params: any) => {
                    const url = region === 'KR'
                        ? `https://finance.naver.com/item/main.nhn?code=${params.value}`
                        : `https://finance.yahoo.com/quote/${params.value}`;
                    return <span className="font-bold cursor-pointer text-blue-400" onClick={() => window.open(url, '_blank')}>{params.value}</span>
                }
            },
            { field: 'name', headerName: 'Name', width: 150, filter: true },
            { field: 'industry', headerName: 'Industry', width: 130 },
            {
                field: 'marketcap', headerName: 'Market Cap', width: 110, valueFormatter: (p) => {
                    if (!p.value) return '-';
                    if (region === 'KR') {
                        // Korean Format: Jo + Eok
                        const val = p.value;
                        if (val >= 1000000000000) { // 1 Trillion
                            const jo = Math.floor(val / 1000000000000);
                            const eok = Math.round((val % 1000000000000) / 100000000);
                            return eok > 0 ? `${jo}조 ${eok}억` : `${jo}조`;
                        }
                        const eok = Math.round(val / 100000000);
                        return `${eok}억`;
                    }
                    // Billion unit
                    const val = p.value / 1000000000;
                    return '$' + val.toLocaleString(undefined, { maximumFractionDigits: 1 }) + 'B';
                }
            },
        ];

        if (region === 'KR') {
            return [
                ...common,
                // Z-Scores First
                { field: 'pricez', headerName: 'Price Z', width: 90, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'perz', headerName: 'PER Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'pbrz', headerName: 'PBR Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'psrz', headerName: 'PSR Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'ev_ebitdaz', headerName: 'EV/EBITDA Z', width: 110, valueFormatter: (p) => p.value?.toFixed(1) },

                // Metrics
                { field: 'per', headerName: 'PER', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'pbr', headerName: 'PBR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'psr', headerName: 'PSR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'ev_ebitda', headerName: 'EV/EBITDA', width: 100, valueFormatter: (p) => p.value?.toFixed(1) },

                { field: 'sales_growth', headerName: 'Sales Gr', width: 90, valueFormatter: (p) => p.value?.toFixed(0) + '%' },
                { field: 'op_growth', headerName: 'OP Gr', width: 90, valueFormatter: (p) => p.value?.toFixed(0) + '%' },
                { field: 'np_growth', headerName: 'NP Gr', width: 90, valueFormatter: (p) => p.value?.toFixed(0) + '%' },

                {
                    headerName: 'Target',
                    width: 100,
                    cellRenderer: () => <span className="cursor-pointer text-yellow-400">View</span>,
                    onCellClicked: () => setSelectedColumn('consensus')
                },
                { field: 'target_price', headerName: 'Avg Target', width: 100, valueFormatter: (p) => p.value ? p.value.toLocaleString() : '-' },
                { field: 'current_price', headerName: 'Current Price', width: 100, valueFormatter: (p) => p.value ? p.value.toLocaleString() : '-' },
                {
                    field: 'upside',
                    headerName: 'Upside',
                    width: 90,
                    cellStyle: params => {
                        if (params.value > 0) return { color: '#4ade80' };
                        if (params.value < 0) return { color: '#f87171' };
                        return null;
                    },
                    valueFormatter: (p) => (p.value !== undefined && p.value !== null) ? p.value.toFixed(1) + '%' : '-'
                },
            ];
        } else {
            // US Columns
            return [
                ...common,
                // Z-Scores First
                { field: 'pricez', headerName: 'Price Z', width: 90, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'perz', headerName: 'PER Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1), cellStyle: { color: '#aaa' } },
                { field: 'pbrz', headerName: 'PBR Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1), cellStyle: { color: '#aaa' } },
                { field: 'psrz', headerName: 'PSR Z', width: 80, valueFormatter: (p) => p.value?.toFixed(1), cellStyle: { color: '#aaa' } },
                { field: 'ev_ebitdaz', headerName: 'EV/EBITDA Z', width: 110, valueFormatter: (p) => p.value?.toFixed(1), cellStyle: { color: '#aaa' } },

                // Metrics
                { field: 'per', headerName: 'PER', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'pbr', headerName: 'PBR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'psr', headerName: 'PSR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'ev_ebitda', headerName: 'EV/EBITDA', width: 100, valueFormatter: (p) => p.value?.toFixed(1) },

                { field: 'pcr', headerName: 'PCR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'por', headerName: 'POR', width: 80, valueFormatter: (p) => p.value?.toFixed(1) },
                { field: 'yield', headerName: 'Yield', width: 80, valueFormatter: (p) => p.value?.toFixed(1) + '%' },

                {
                    headerName: 'Target',
                    width: 100,
                    cellRenderer: () => <span className="cursor-pointer text-yellow-400">View</span>,
                    onCellClicked: () => setSelectedColumn('consensus')
                },
                { field: 'target_price', headerName: 'Avg Target', width: 100, valueFormatter: (p) => p.value ? p.value.toLocaleString() : '-' },
                { field: 'current_price', headerName: 'Current Price', width: 100, valueFormatter: (p) => p.value ? '$' + p.value.toFixed(2) : '-' },
                {
                    field: 'upside',
                    headerName: 'Upside',
                    width: 90,
                    cellStyle: params => {
                        if (params.value > 0) return { color: '#4ade80' };
                        if (params.value < 0) return { color: '#f87171' };
                        return null;
                    },
                    valueFormatter: (p) => (p.value !== undefined && p.value !== null) ? p.value.toFixed(1) + '%' : '-'
                },
            ];
        }
    }, [region]);

    const defaultColDef = useMemo(() => ({
        sortable: true,
        filter: true,
        resizable: true,
        floatingFilter: false,
    }), []);

    const onCellClicked = (event: any) => {
        if (event.colDef.field === 'ticker') return;
        if (event.colDef.headerName === 'Target') {
            setSelectedTicker(event.data.ticker);
            setSelectedColumn('consensus');
            return;
        }

        setSelectedTicker(event.data.ticker);

        let field = event.colDef.field;
        if (!field) return;

        if (['per', 'pbr', 'psr', 'ev_ebitda', 'pcr', 'por', 'yield', 'perz', 'pbrz', 'psrz', 'ev_ebitdaz'].includes(field)) {
            let col = field;
            // If field is Z score already e.g. perz, keep it
            // If field is metric e.g. per, add z
            // Wait, chart expects 'perz' etc.
            if (col.endsWith('z')) {
                // perz -> perz
            } else {
                col = col + 'z'; // per -> perz
            }
            setSelectedColumn(col);
        } else {
            setSelectedColumn('pricez');
        }
    };

    return (
        <main className="flex flex-col min-h-screen p-4 bg-gray-900 text-white">
            <nav className="flex items-center justify-between p-4 bg-gray-800 rounded mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-xl font-bold font-serif">ANTS Investment</span>
                    <div className="flex bg-gray-700 rounded ml-4">
                        <button
                            className={`px-3 py-1 rounded ${region === 'KR' ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'}`}
                            onClick={() => setRegion('KR')}
                        >
                            KR
                        </button>
                        <button
                            className={`px-3 py-1 rounded ${region === 'US' ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'}`}
                            onClick={() => setRegion('US')}
                        >
                            US
                        </button>
                    </div>
                </div>
            </nav>

            {/* Infinite Scroll: Fixed Height Container + No Pagination */}
            <div className="w-full h-[calc(100vh-180px)] bg-gray-900 text-white mb-4 rounded overflow-hidden ag-theme-quartz-dark">
                <AgGridReact
                    rowData={rowData}
                    columnDefs={colDefs}
                    defaultColDef={defaultColDef}
                    onCellClicked={onCellClicked}
                    rowSelection='single'
                // pagination={true} // Removed for Infinite Scroll
                // paginationPageSize={10} // Removed
                // domLayout='autoHeight' // Removed to allow internal scroll
                />
            </div>

            <div className="flex-1 w-full bg-gray-800 rounded p-4 min-h-[500px]">
                {selectedTicker ? (
                    selectedColumn === 'consensus' ? (
                        <ConsensusTable ticker={selectedTicker} region={region} />
                    ) : (
                        <DynamicChart ticker={selectedTicker} columnId={selectedColumn} />
                    )
                ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                        Select a ticker to view chart
                    </div>
                )}
            </div>
        </main>
    );
}
