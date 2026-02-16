'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, SeriesType } from 'lightweight-charts';
import { getPath } from '@/utils/path';

interface ChartProps {
    ticker: string;
    columnId: string; // e.g. 'pricez', 'perz', 'pbrz'
}

export default function Chart({ ticker, columnId }: ChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartInstance = useRef<IChartApi | null>(null);

    // Refs for series to update data without recreating chart
    const candlestickSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
    const lineSeriesRefs = useRef<ISeriesApi<'Line'>[]>([]);

    const [chartData, setChartData] = useState<any[]>([]);

    useEffect(() => {
        // Fetch data when ticker changes
        if (!ticker) return;

        // Detect region: KR tickers are numeric (e.g. 005930), US are letters (AAPL)
        const isKR = /^\d+$/.test(ticker);
        const path = isKR
            ? getPath(`data/details/${ticker}.json`)
            : getPath(`data/us/Details/${ticker}.json`);

        fetch(path)
            .then(res => res.json())
            .then(data => {
                // Convert dates to string slightly if needed, but they are YYYY-MM-DD
                setChartData(data);
            })
            .catch(err => {
                console.error("Error fetching chart data", err);
                setChartData([]); // Reset on error
            });
    }, [ticker]);

    useEffect(() => {
        if (!chartContainerRef.current) return;
        if (chartData.length === 0) return;
        if (chartContainerRef.current.clientWidth === 0) {
            // Wait for resize? 
            return;
        }

        // cleanup previous chart
        if (chartInstance.current) {
            try {
                chartInstance.current.remove();
            } catch (e) {
                console.warn("Failed to remove chart", e);
            }
            chartInstance.current = null;
        }

        try {
            const chart = createChart(chartContainerRef.current, {
                layout: {
                    background: { type: ColorType.Solid, color: '#1f2937' }, // gray-800 matches container
                    textColor: '#d1d5db', // gray-300 or white
                },
                width: chartContainerRef.current.clientWidth,
                height: 500,
                grid: {
                    vertLines: { color: 'rgba(255, 255, 255, 0.1)' },
                    horzLines: { color: 'rgba(255, 255, 255, 0.1)' },
                },
                timeScale: {
                    rightOffset: 12,
                    barSpacing: 3,
                    fixLeftEdge: true,
                    lockVisibleTimeRangeOnResize: true,
                    rightBarStaysOnScroll: true,
                    borderVisible: false,
                    visible: true,
                    timeVisible: true,
                    secondsVisible: false,
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                },
                rightPriceScale: {
                    borderColor: 'rgba(255, 255, 255, 0.2)',
                }
            });
            chartInstance.current = chart;

            // Logic to calculate bands
            const getBands = (data: any[], colId: string) => {
                // Determine Indicator
                let indicator = '';
                let perShareKey = '';

                if (colId === 'pricez') {
                    // Price Z-Score (Regression)
                    // Bands = BASE + z * std_dev
                    const residuals = data.map(d => {
                        if (d.CLOSE === undefined || d.BASE === undefined) return NaN;
                        return d.CLOSE - d.BASE;
                    }).filter(v => typeof v === 'number' && !isNaN(v));

                    if (residuals.length < 2) return [];

                    // Calculate StdDev of Residuals
                    const meanRes = residuals.reduce((a, b) => a + b, 0) / residuals.length;
                    const variance = residuals.reduce((a, b) => a + (b - meanRes) ** 2, 0) / (residuals.length - 1);
                    const stdDev = Math.sqrt(variance);

                    if (isNaN(stdDev)) return [];

                    const bandSeries = [];
                    const zs = [2.0, 1.5, 1.0, 0.5, 0.0, -0.5, -1.0, -1.5, -2.0];
                    const props = [
                        { color: 'darkred', width: 1, style: 3 }, // +2.0
                        { color: 'darkred', width: 1, style: 2 }, // +1.5
                        { color: 'red', width: 1, style: 3 },     // +1.0
                        { color: 'red', width: 1, style: 2 },     // +0.5
                        { color: 'dimgray', width: 1, style: 3 }, // 0.0
                        { color: 'blue', width: 1, style: 2 },    // -0.5
                        { color: 'blue', width: 1, style: 3 },    // -1.0
                        { color: 'darkblue', width: 1, style: 2 },// -1.5
                        { color: 'darkblue', width: 1, style: 3 },// -2.0
                    ];

                    for (let i = 0; i < zs.length; i++) {
                        const z = zs[i];
                        const seriesData = data.map(d => {
                            const val = d.BASE + z * stdDev;
                            if (isNaN(val)) return null;
                            return {
                                time: d.DATE,
                                value: val
                            };
                        }).filter(d => d !== null);
                        bandSeries.push({ data: seriesData, options: props[i] });
                    }
                    return bandSeries;

                } else {
                    // Fundamental Z-Score
                    if (colId.includes('per')) { indicator = 'PER'; perShareKey = 'ADJ_EPS'; }
                    else if (colId.includes('pbr')) { indicator = 'PBR'; perShareKey = 'ADJ_BPS'; }
                    else if (colId.includes('psr')) { indicator = 'PSR'; perShareKey = 'ADJ_SPS'; }
                    else if (colId.includes('ev_ebitda')) { indicator = 'EV_EBITDA'; perShareKey = 'ADJ_EBITDA'; }
                    else if (colId.includes('pcr')) { indicator = 'PCR'; perShareKey = 'ADJ_CPS'; }
                    else if (colId.includes('por')) { indicator = 'POR'; perShareKey = 'ADJ_OPS'; }
                    else if (colId.includes('yield')) { indicator = 'YIELD'; perShareKey = ''; } // Ratio is %

                    // Get Mean and Std of Indicator
                    const validValues = data.map(d => d[indicator]).filter(v => v !== 0 && v !== undefined && v !== null && !isNaN(v));
                    if (validValues.length === 0) return [];

                    const mean = validValues.reduce((a, b) => a + b, 0) / validValues.length;
                    const variance = validValues.reduce((a, b) => a + (b - mean) ** 2, 0) / validValues.length;
                    const std = Math.sqrt(variance);

                    const bandSeries = [];
                    const zs = [2.0, 1.5, 1.0, 0.5, 0.0, -0.5, -1.0, -1.5, -2.0];
                    const props = [
                        { color: 'darkred', width: 1, style: 3 },
                        { color: 'darkred', width: 1, style: 2 },
                        { color: 'red', width: 1, style: 3 },
                        { color: 'red', width: 1, style: 2 },
                        { color: 'dimgray', width: 1, style: 3 },
                        { color: 'blue', width: 1, style: 2 },
                        { color: 'blue', width: 1, style: 3 },
                        { color: 'darkblue', width: 1, style: 2 },
                        { color: 'darkblue', width: 1, style: 3 },
                    ];

                    for (let i = 0; i < zs.length; i++) {
                        const z = zs[i];
                        const seriesData = data.map(d => {
                            let val = 0;
                            if (indicator === 'EV_EBITDA') {
                                const ratio = mean + z * std;
                                const ebitda = d['ADJ_EBITDA'] || 0;
                                const debt = d['ADJ_DEBT_CASH'] || 0;
                                const share = d['SHARE'] || 1;
                                val = (ratio * ebitda + debt) / share;
                            } else if (indicator === 'YIELD') {
                                // Yield Band (Inverse)
                                // Target Yield = Mean + Z*Std
                                // Implied Price = Dividend / (Target Yield / 100)
                                // Dividend = (d.YIELD / 100) * d.CLOSE
                                const currentYield = d['YIELD'] || 0;
                                const close = d['CLOSE'] || d['Close'] || 0; // JSON uses CLOSE? Yes script set CLOSE
                                const dps = (currentYield / 100) * close; // Recover DPS

                                const targetYield = mean + z * std;

                                if (dps > 0 && targetYield > 0.1) { // Avoid div by zero or almost zero yield
                                    val = dps / (targetYield / 100);
                                } else {
                                    val = 0;
                                }
                            } else {
                                const ratio = mean + z * std;
                                const ps = d[perShareKey] || 0;
                                val = ratio * ps;
                            }
                            if (val < 0) val = 0;
                            // Clamp huge values?
                            return { time: d.DATE, value: val };
                        });
                        bandSeries.push({ data: seriesData, options: props[i] });
                    }
                    return bandSeries;
                }
            };

            // 1. Candlestick Series
            const candlestickSeries = chart.addCandlestickSeries();
            const ohlcData = chartData.map(d => ({
                time: d.DATE,
                open: d.OPEN,
                high: d.HIGH,
                low: d.LOW,
                close: d.CLOSE,
            })).filter(d => d.time && !isNaN(d.open) && !isNaN(d.close));

            // Validate data sorting?
            // chartData usually sorted.
            candlestickSeries.setData(ohlcData);

            // 2. Band Series
            // [Insert getBands Logic Here or assume it's moved/referenced]
            const bands = getBands(chartData, columnId);
            bands.forEach(band => {
                const series = chart.addLineSeries({
                    color: band.options.color,
                    lineWidth: band.options.width as any,
                    lineStyle: band.options.style as any,
                    lastValueVisible: false,
                    priceLineVisible: false,
                    crosshairMarkerVisible: false,
                });
                series.setData(band.data);
            });

            chart.timeScale().fitContent();

            const handleResize = () => {
                if (chartContainerRef.current && chartInstance.current) {
                    chartInstance.current.applyOptions({ width: chartContainerRef.current.clientWidth });
                }
            };

            window.addEventListener('resize', handleResize);

            return () => {
                window.removeEventListener('resize', handleResize);
                if (chartInstance.current) {
                    try {
                        chartInstance.current.remove();
                    } catch (e) { }
                    chartInstance.current = null;
                }
            };
        } catch (err) {
            console.error("Chart Creation/Update Error:", err);
        }

    }, [chartData, columnId]);

    const setRange = (period: string) => {
        if (!chartInstance.current || chartData.length === 0) return;

        const timeScale = chartInstance.current.timeScale();

        if (period === 'ALL') {
            timeScale.fitContent();
        } else {
            // Calculate Start Date
            const days = period === '1Y' ? 365 : period === '3Y' ? 1095 : period === '5Y' ? 1825 : 3650; // 10Y

            // Get last date from data
            const lastPoint = chartData[chartData.length - 1];
            if (!lastPoint) return;

            const lastDate = new Date(lastPoint.DATE);
            const startDate = new Date(lastDate);
            startDate.setDate(startDate.getDate() - days);

            const fromStr = startDate.toISOString().split('T')[0];
            const toStr = lastDate.toISOString().split('T')[0];

            timeScale.setVisibleRange({
                from: fromStr,
                to: toStr
            });
        }
    };

    return (
        <div className="relative w-full h-full">
            <div className="absolute top-2 right-2 z-10 flex gap-2">
                {['1Y', '3Y', '5Y', 'ALL'].map((r) => (
                    <button
                        key={r}
                        className="bg-gray-700 hover:bg-gray-600 text-xs text-white px-2 py-1 rounded"
                        onClick={() => setRange(r)}
                    >
                        {r}
                    </button>
                ))}
            </div>
            <div ref={chartContainerRef} className="w-full h-[500px]" />
        </div>
    );
}
