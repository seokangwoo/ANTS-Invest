'use client';

import React, { useEffect, useState, useRef } from 'react';
import { getPath } from '@/utils/path';

interface ConsensusItem {
    date: string;
    firm: string;
    action: string;
    grade_from: string;
    grade_to: string;
    target: number;
}

interface Props {
    ticker: string;
    region: 'KR' | 'US';
}

export default function ConsensusTable({ ticker, region }: Props) {
    const [rowData, setRowData] = useState<ConsensusItem[]>([]);
    const scrollRef = useRef<HTMLDivElement>(null);
    const [isDragging, setIsDragging] = useState(false);
    const [startX, setStartX] = useState(0);
    const [startY, setStartY] = useState(0);
    const [scrollLeft, setScrollLeft] = useState(0);
    const [scrollTop, setScrollTop] = useState(0);

    useEffect(() => {
        if (!ticker) return;

        const basePath = region === 'KR' ? 'data/kr/Consensus' : 'data/us/Consensus';
        const path = getPath(`${basePath}/${ticker}.json`);

        fetch(path)
            .then(res => res.json())
            .then(data => {
                if (!data) {
                    setRowData([]);
                    return;
                }

                if (region === 'KR') {
                    // Map KR KIS data to ConsensusItem
                    const mapped = data.map((item: any) => ({
                        date: item.stck_bsop_date ? `${item.stck_bsop_date.substring(0, 4)}-${item.stck_bsop_date.substring(4, 6)}-${item.stck_bsop_date.substring(6, 8)}` : '',
                        firm: item.mbcr_name,
                        action: item.invt_opnn,
                        grade_from: '',
                        grade_to: '',
                        target: parseInt(item.hts_goal_prc || '0')
                    }));

                    // Sort by date desc
                    mapped.sort((a: ConsensusItem, b: ConsensusItem) => b.date.localeCompare(a.date));
                    setRowData(mapped);
                } else {
                    setRowData(data);
                }
            })
            .catch(err => {
                console.error("Failed to fetch consensus", err);
                setRowData([]);
            });
    }, [ticker, region]);

    // Drag to Scroll Logic
    const onMouseDown = (e: React.MouseEvent) => {
        if (!scrollRef.current) return;
        setIsDragging(true);
        setStartX(e.pageX - scrollRef.current.offsetLeft);
        setStartY(e.pageY - scrollRef.current.offsetTop);
        setScrollLeft(scrollRef.current.scrollLeft);
        setScrollTop(scrollRef.current.scrollTop);
    };

    const onMouseLeave = () => {
        setIsDragging(false);
    };

    const onMouseUp = () => {
        setIsDragging(false);
    };

    const onMouseMove = (e: React.MouseEvent) => {
        if (!isDragging || !scrollRef.current) return;
        e.preventDefault();
        const x = e.pageX - scrollRef.current.offsetLeft;
        const y = e.pageY - scrollRef.current.offsetTop;
        const walkX = (x - startX) * 1.5; // Scroll speed multiplier
        const walkY = (y - startY) * 1.5;
        scrollRef.current.scrollLeft = scrollLeft - walkX;
        scrollRef.current.scrollTop = scrollTop - walkY;
    };

    if (rowData.length === 0) {
        return (
            <div className="w-full text-center p-4 text-gray-500">
                {region === 'KR' ? "Consensus history not available for KR yet." : "No consensus data found."}
            </div>
        );
    }

    return (
        <div className="w-full h-auto bg-gray-900 text-white rounded overflow-hidden shadow-lg border border-gray-700">
            <div className="p-3 border-b border-gray-700 font-bold bg-gray-800 flex justify-between items-center">
                <span>⚠️ Analyst Consensus History (Recent)</span>
                <span className="text-xs text-gray-400 font-normal">Drag to scroll</span>
            </div>

            <div
                ref={scrollRef}
                className="h-[400px] overflow-auto cursor-grab active:cursor-grabbing select-none"
                onMouseDown={onMouseDown}
                onMouseLeave={onMouseLeave}
                onMouseUp={onMouseUp}
                onMouseMove={onMouseMove}
            >
                <table className="w-full text-sm text-left">
                    <thead className="text-xs text-gray-400 uppercase bg-gray-800 sticky top-0 z-10">
                        <tr>
                            <th className="px-4 py-3">Date</th>
                            <th className="px-4 py-3">Firm</th>
                            <th className="px-4 py-3">Opinion</th>
                            <th className="px-4 py-3 text-right">Target Price</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rowData.map((item, index) => (
                            <tr key={index} className="border-b border-gray-800 hover:bg-gray-800/50 transition-colors">
                                <td className="px-4 py-3 font-medium text-gray-300 whitespace-nowrap">{item.date}</td>
                                <td className="px-4 py-3 text-blue-400 whitespace-nowrap">{item.firm}</td>
                                <td className={`px-4 py-3 font-bold whitespace-nowrap ${item.action === 'BUY' || item.action === '매수' ? 'text-green-400' :
                                        item.action === 'SELL' || item.action === '매도' ? 'text-red-400' : 'text-yellow-400'
                                    }`}>
                                    {item.action}
                                </td>
                                <td className="px-4 py-3 text-right font-mono text-gray-300 whitespace-nowrap">
                                    {item.target > 0 ? (region === 'KR' ? item.target.toLocaleString() : `$${item.target}`) : '-'}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
