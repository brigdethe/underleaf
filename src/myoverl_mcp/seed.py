from myoverl_mcp.ids import new_id
from myoverl_mcp.models import (
    Bullet,
    Entry,
    Heading,
    Resume,
    Section,
    SkillRow,
    stencil_contact,
)
from myoverl_mcp.store import ResumeStore


def _bullets(*texts: str) -> list[Bullet]:
    return [Bullet(bullet_id=new_id("bul"), text=text) for text in texts]


def seed_bright(store: ResumeStore) -> Resume:
    resume_id = new_id("res")
    resume = Resume(
        resume_id=resume_id,
        name="Bright",
        role="source",
        editor_url=f"https://example.invalid/r/{resume_id}",
        heading=Heading(
            name="Bright Owusu",
            slots=[
                stencil_contact(
                    kind="phone",
                    href="tel:+13182658445",
                    text="(318) 265-8445",
                ),
                stencil_contact(
                    kind="email",
                    href="mailto:owusuomaribright@gmail.com",
                    text=None,
                ),
                stencil_contact(
                    kind="linkedin",
                    href="https://www.linkedin.com/in/owusuomaribright",
                    text=None,
                ),
                stencil_contact(
                    kind="portfolio",
                    href="https://omari.is-a.dev",
                    text=None,
                ),
            ],
        ),
        sections=[
            Section(
                section_id=new_id("sec"),
                kind="education",
                title="Education",
                entries=[
                    Entry(
                        entry_id=new_id("ent"),
                        kind="education",
                        title="Bachelor of Science in Cybersecurity",
                        fields={
                            "school": "Grambling State University",
                            "location": "Grambling, LA",
                            "degree": "Bachelor of Science in Cybersecurity",
                            "dates": "Aug. 2024 -- May 2028",
                        },
                        honors=[
                            "Dean's List",
                            "Earl Lester Cole Honors College",
                            "Code2040",
                            "NSBE",
                            "ColorStack",
                        ],
                        coursework=[
                            "Data Structures & Algorithms",
                            "Intro to AI",
                            "Operating Systems & Security",
                            "Databases and Data Security",
                            "Intrusion Detection and Protection",
                        ],
                    )
                ],
            ),
            Section(
                section_id=new_id("sec"),
                kind="experience",
                title="Experience",
                entries=[
                    Entry(
                        entry_id=new_id("ent"),
                        kind="experience",
                        title="Product Security Engineering Intern",
                        fields={
                            "company": "Palo Alto Networks",
                            "dates": "May 2026 -- Aug 2026",
                            "location": "Santa Clara, CA",
                        },
                        bullets=_bullets(
                            "Automated privileged-access provisioning across 6 tenants, leveraging Apache Airflow and Microsoft Graph APIs to streamline request intake, approvals, and Entra group additions",
                            "Cut on-call response time for 1,500+ engineers (6 min to 30s) by building a Slack agent on Vertex AI, retrieving context from Jira, BigQuery, and security playbooks",
                            "Achieved 90% answer accuracy across 400 threads by building deterministic Python middleware between LLM calls",
                            "Accelerated IAM policy resolution across GCP, AWS, and Azure by deploying agentic workflows via Terraform",
                        ),
                    ),
                    Entry(
                        entry_id=new_id("ent"),
                        kind="experience",
                        title="AI Automation Extern",
                        fields={
                            "company": "Wayfair -- Extern",
                            "dates": "Jan 2026 -- Mar 2026",
                            "location": "Remote",
                        },
                        bullets=_bullets(
                            "Scaled market tracking of 1M+ product records by building an ETL pipeline scraping over 200+ sites with Gemini",
                            "Reduced intelligence reporting time from hours to <2 mins by syncing ETL data with Sheets via Google ADK",
                            "Cut per-inference spend by 60% ($0.17 to $0.07) by deploying a LiteLLM router optimizing model selection",
                        ),
                    ),
                    Entry(
                        entry_id=new_id("ent"),
                        kind="experience",
                        title="Software Engineering Intern",
                        fields={
                            "company": "Maddy Group Ltd.",
                            "dates": "May 2025 -- Aug 2025",
                            "location": "Remote",
                        },
                        bullets=_bullets(
                            "Hardened identity management for 200+ employees by developing a 4-role RBAC publishing system integrating a React frontend with a PHP backend via REST APIs",
                            "Fortified database security in PostgreSQL by enforcing prepared statements and strict parameterized queries",
                            "Ensured backend stability by reaching 92% test coverage via 70+ Pytest unit and integration tests",
                            "Accelerated API adoption for 6 dev teams by publishing standard integration documentation on Confluence",
                        ),
                    ),
                ],
            ),
            Section(
                section_id=new_id("sec"),
                kind="projects",
                title="Projects",
                entries=[
                    Entry(
                        entry_id=new_id("ent"),
                        kind="project",
                        title="Immigration Assistant (Best Overall Project, Code2040 TFR Hackathon)",
                        technologies=[
                            "Python",
                            "LangChain",
                            "PyTorch",
                            "React",
                            "Gemini",
                        ],
                        link_url="https://omariomari2.github.io/webpager/",
                        bullets=_bullets(
                            "Led 3 engineers to build a RAG pipeline over 500K+ lines of USCIS policy using LangChain, achieving 88% answer accuracy on a human-annotated eval set of 200 Q&A pairs",
                            "Secured user PII and sensitive queries by generating on-device embeddings via PyTorch to bypass external APIs",
                            "Cut deployment overhead by automating a continuous local to GCP-VM CI/CD pipeline with GitHub Actions",
                        ),
                    ),
                    Entry(
                        entry_id=new_id("ent"),
                        kind="project",
                        title="Uncluster -- Code Migration Engine",
                        technologies=[
                            "Golang",
                            "Fiber v2",
                            "REST API",
                            "TypeScript",
                            "JavaScript",
                        ],
                        link_url="https://uncluster-production.up.railway.app/how-it-works.html",
                        bullets=_bullets(
                            "Built an LLM-free compiler using DFS with 70+ translation rules to generate type-safe TypeScript from HTML",
                            "Prevented state corruption and race conditions by enforcing idempotency keys via a Fiber REST API wrapper",
                        ),
                    ),
                    Entry(
                        entry_id=new_id("ent"),
                        kind="project",
                        title="WVS 1.01 -- PANW ShadowBank CTF",
                        technologies=[
                            "Linux",
                            "Python",
                            "GitHub Actions",
                            "Docker",
                        ],
                        link_url=None,
                        bullets=_bullets(
                            "Integrated 4 SASTs into GitHub Actions with deduplication and retry logic to flag 50+ CVEs in AI-generated PRs",
                            "Cut scan times by half by writing Bash scripts to run SASTs concurrently in Linux Docker containers",
                            "Engineered a custom MCP server in Cursor, enabling AI agents to auto-patch CVEs using NIST standards",
                        ),
                    ),
                ],
            ),
            Section(
                section_id=new_id("sec"),
                kind="skills",
                title="Technical Skills",
                skill_rows=[
                    SkillRow(
                        row_id=new_id("row"),
                        title="Languages",
                        items=[
                            "Python",
                            "Go",
                            "TypeScript",
                            "JavaScript",
                            "C++",
                            "PHP",
                            "Bash",
                            "SQL",
                        ],
                    ),
                    SkillRow(
                        row_id=new_id("row"),
                        title="Frameworks",
                        items=[
                            "Flask",
                            "FastAPI",
                            "React",
                            "Vite",
                            "Fiber v2",
                            "LangChain",
                            "PyTorch",
                            "Google ADK",
                            "LiteLLM",
                        ],
                    ),
                    SkillRow(
                        row_id=new_id("row"),
                        title="Developer Tools",
                        items=[
                            "GCP",
                            "AWS",
                            "Azure",
                            "Terraform",
                            "Docker",
                            "GitHub Actions",
                            "Apache Airflow",
                            "Pytest",
                            "Bitbucket",
                        ],
                    ),
                ],
            ),
            Section(
                section_id=new_id("sec"),
                kind="extracurriculars",
                title="Extracurriculars",
                entries=[
                    Entry(
                        entry_id=new_id("ent"),
                        kind="extracurricular",
                        title="Google Student Developer",
                        fields={"dates": "Jun 2025 -- Present"},
                        bullets=_bullets(
                            "Solved complex algorithmic challenges in C++, optimizing for strict time and space complexities",
                            "Enforced secure coding practices under mentor-led code reviews across 50K+ lines of code via Google Colab",
                        ),
                    )
                ],
            ),
        ],
    )
    return store.put(resume)
