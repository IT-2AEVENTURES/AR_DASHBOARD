'use client';

import dynamic from 'next/dynamic';

const Plot = dynamic(() => import('react-plotly.js'), { ssr: false });

export default function PlotComponent({ data, layout, config }: any) {
  return (
    <Plot
      data={data}
      layout={{...layout, autosize: true}}
      config={config}
      useResizeHandler={true}
      style={{ width: '100%', height: '100%' }}
    />
  );
}
