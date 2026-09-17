document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const loadingSpinner = document.getElementById('loading-spinner');
    const emptyState = document.getElementById('empty-state');
    const heroSection = document.getElementById('hero-section');
    const archiveSection = document.getElementById('archive-section');
    const latestSummaryCard = document.getElementById('latest-summary-card');
    const archiveGrid = document.getElementById('archive-grid');

    let allSummaries = [];

    // API 호출을 통해 data.json을 불러옵니다.
    async function fetchSummaries() {
        try {
            const response = await fetch('data.json');
            if (!response.ok) {
                throw new Error('데이터 파일을 읽을 수 없습니다.');
            }
            allSummaries = await response.json();
            renderDashboard(allSummaries);
        } catch (error) {
            console.error('Error fetching summaries:', error);
            // 오류 시 빈 배열 처리 및 에러 안내
            allSummaries = [];
            renderDashboard([]);
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    }

    // 날짜 포맷팅 (YYYY.MM.DD)
    function formatDate(isoString) {
        if (!isoString) return '';
        try {
            const date = new Date(isoString);
            return `${date.getFullYear()}. ${String(date.getMonth() + 1).padStart(2, '0')}. ${String(date.getDate()).padStart(2, '0')}`;
        } catch (e) {
            return isoString.substring(0, 10);
        }
    }

    // 카드 내부 HTML 템플릿 생성
    def_card_html = (item, isHero = false) => {
        const { id, title, published, summary } = item;
        
        // 챕터 리스트 빌드
        let chaptersHtml = '';
        if (summary.chapters && summary.chapters.length > 0) {
            chaptersHtml = summary.chapters.map(ch => {
                // 타임라인 초 계산 (예: '02:15' -> 135)
                let timeSeconds = 0;
                if (ch.timeline) {
                    const parts = ch.timeline.split(':');
                    if (parts.length === 2) {
                        timeSeconds = parseInt(parts[0]) * 60 + parseInt(parts[1]);
                    } else if (parts.length === 3) {
                        timeSeconds = parseInt(parts[0]) * 3600 + parseInt(parts[1]) * 60 + parseInt(parts[2]);
                    }
                }
                
                return `
                    <div class="chapter-item">
                        <div class="chapter-header">
                            <a href="https://www.youtube.com/watch?v=${id}&t=${timeSeconds}s" 
                               target="_blank" 
                               class="chapter-timeline" 
                               title="해당 시간대로 유튜브 영상 이동">
                               ${ch.timeline || '00:00'} 🔗
                            </a>
                            <span class="chapter-title">${ch.title}</span>
                        </div>
                        <p class="chapter-content">${ch.content}</p>
                    </div>
                `;
            }).join('');
        }

        // 키워드 태그 빌드
        let keywordsHtml = '';
        if (summary.keywords && summary.keywords.length > 0) {
            keywordsHtml = summary.keywords.map(kw => `
                <span class="keyword-tag">#${kw}</span>
            `).join('');
        }

        // 아카이브 카드의 경우 접을 수 있는 영역 처리
        const contentStart = isHero ? '' : '<div class="collapsible-content">';
        const contentEnd = isHero ? '' : '</div>';
        
        // 접힘 상태 아이콘 (아카이브 카드만)
        const expandIndicator = isHero ? '' : `
            <div class="card-expand-indicator">
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"></polyline></svg>
            </div>
        `;

        return `
            <div class="card-header">
                <div class="card-meta">
                    <span class="card-date">${formatDate(published)}</span>
                    <a href="https://www.youtube.com/watch?v=${id}" target="_blank" class="yt-link">
                        📺 YouTube 원본 보기
                    </a>
                </div>
                <h3 class="card-title">${title}</h3>
            </div>
            
            <div class="one-liner-box">
                💡 ${summary.one_liner || '요약 정보가 없습니다.'}
            </div>
            
            <div class="keywords-container">
                ${keywordsHtml}
            </div>

            ${contentStart}
                <div class="chapters-wrapper">
                    ${chaptersHtml}
                </div>
                
                <div class="insights-box">
                    <div class="insights-title">Editor's Insights</div>
                    <div class="insights-content">${summary.insights || ''}</div>
                </div>
            ${contentEnd}
            
            ${expandIndicator}
        `;
    };

    // 대시보드 화면 렌더링
    function renderDashboard(items) {
        if (!items || items.length === 0) {
            heroSection.classList.add('hidden');
            archiveSection.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');

        // 1. 최신 요약 (배열 첫 번째 항목)
        const latest = items[0];
        latestSummaryCard.innerHTML = def_card_html(latest, true);
        latestSummaryCard.className = 'summary-card hero-card';
        heroSection.classList.remove('hidden');

        // 2. 아카이브 목록 (나머지 항목들)
        const archiveItems = items.slice(1);
        if (archiveItems.length > 0) {
            archiveGrid.innerHTML = '';
            archiveItems.forEach(item => {
                const card = document.createElement('article');
                card.className = 'summary-card archive-card';
                card.innerHTML = def_card_html(item, false);
                
                // 클릭하여 상세 요약 펼치기/접기 인터랙션
                card.addEventListener('click', (e) => {
                    // 유튜브 원본 링크나 타임라인 앵커 클릭 시 토글 방지
                    if (e.target.closest('a')) {
                        return;
                    }
                    card.classList.toggle('expanded');
                });

                archiveGrid.appendChild(card);
            });
            archiveSection.classList.remove('hidden');
        } else {
            archiveSection.classList.add('hidden');
        }
    }

    // 실시간 검색 로직
    function handleSearch() {
        const query = searchInput.value.toLowerCase().trim();
        
        if (!query) {
            // 검색어가 없을 때는 기본 구조로 정상 렌더링
            renderDashboard(allSummaries);
            return;
        }

        // 검색 필터링
        const filtered = allSummaries.filter(item => {
            const titleMatch = item.title.toLowerCase().includes(query);
            const oneLinerMatch = (item.summary.one_liner || '').toLowerCase().includes(query);
            const insightsMatch = (item.summary.insights || '').toLowerCase().includes(query);
            
            // 키워드 검색 매칭
            const keywordsMatch = item.summary.keywords && item.summary.keywords.some(kw => kw.toLowerCase().includes(query));
            
            // 챕터 내용 검색 매칭
            const chaptersMatch = item.summary.chapters && item.summary.chapters.some(ch => 
                ch.title.toLowerCase().includes(query) || ch.content.toLowerCase().includes(query)
            );

            return titleMatch || oneLinerMatch || insightsMatch || keywordsMatch || chaptersMatch;
        });

        // 검색 상태의 렌더링: 검색 시에는 모든 결과를 아카이브 리스트 형태로 전부 펼쳐서 보여줌
        if (filtered.length === 0) {
            heroSection.classList.add('hidden');
            archiveSection.classList.add('hidden');
            emptyState.classList.remove('hidden');
        } else {
            emptyState.classList.add('hidden');
            heroSection.classList.add('hidden'); // 검색 중에는 최신 요약 구분하지 않음
            
            archiveGrid.innerHTML = '';
            filtered.forEach(item => {
                const card = document.createElement('article');
                // 검색 시에는 내용을 바로 볼 수 있도록 expanded 클래스를 기본 적용
                card.className = 'summary-card archive-card expanded';
                card.innerHTML = def_card_html(item, false);
                
                card.addEventListener('click', (e) => {
                    if (e.target.closest('a')) return;
                    card.classList.toggle('expanded');
                });
                
                archiveGrid.appendChild(card);
            });
            archiveSection.classList.remove('hidden');
        }
    }

    // 디바운스 처리하여 검색 입력 효율화
    let searchTimeout;
    searchInput.addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(handleSearch, 200);
    });

    // 시작
    fetchSummaries();
});
