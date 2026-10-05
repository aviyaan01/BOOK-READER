"""Script to generate sample English and Bangla story PDFs for testing."""

from pathlib import Path
import pymupdf as fitz


def generate_sample_books() -> None:
    """Generate sample storybooks in English and Bangla."""
    samples_dir = Path("sample_books")
    samples_dir.mkdir(parents=True, exist_ok=True)

    # 1. English Storybook: The Whispering Tree
    en_doc = fitz.open()
    en_page1 = en_doc.new_page()
    en_page1.insert_text(
        fitz.Point(60, 80),
        "The Whispering Tree and the Starlight Deer",
        fontsize=18,
    )
    en_text_p1 = (
        "High atop the Emerald Mountain stood a grand, ancient tree known as the Whispering Willow. "
        "Its silver leaves sparkled like diamonds beneath the radiant morning sun. "
        "Whenever the wind brushed through its gentle branches, it told ancient tales of magic and wonder. "
        "Every creature in the tranquil forest loved to gather around to listen to its soothing melodies."
    )
    en_page1.insert_textbox(
        fitz.Rect(60, 110, 520, 400),
        en_text_p1,
        fontsize=13,
        lineheight=1.5,
    )

    en_page2 = en_doc.new_page()
    en_text_p2 = (
        "One quiet evening, as twilight painted the sky in shades of violet, a rare Starlight Deer appeared. "
        "Its antlers glowed with warm golden embers, illuminating the mossy path. "
        "\"Do not fear the dark,\" whispered the Willow softly to the forest. "
        "With a gentle nod of courage, the deer leaped across the valley, leaving a sparkling trail of hope behind."
    )
    en_page2.insert_textbox(
        fitz.Rect(60, 80, 520, 400),
        en_text_p2,
        fontsize=13,
        lineheight=1.5,
    )

    en_path = samples_dir / "english_story_whispering_tree.pdf"
    en_doc.save(str(en_path))
    en_doc.close()
    print(f"Created: {en_path}")

    # 2. Bangla Storybook: ছোট্ট নীল ঘুঘু ও সোনালী নদী
    bn_doc = fitz.open()
    nirmala_font_path = "C:/Windows/Fonts/Nirmala.ttf"

    bn_page1 = bn_doc.new_page()
    bn_page1.insert_font(fontname="Nirmala", fontfile=nirmala_font_path)
    bn_page1.insert_text(
        fitz.Point(60, 80),
        "ছোট্ট নীল ঘুঘু ও সোনালী নদী",
        fontname="Nirmala",
        fontsize=18,
    )

    bn_text_p1 = (
        "এক শান্ত সবুজ বনে একটি ছোট্ট নীল ঘুঘু বাস করত। "
        "প্রতিদিন ভোরে ঘুঘুটি মিষ্টি সুরে গান গেয়ে সবাইকে ঘুম থেকে জাগাত। "
        "একদিন সে শুনল বনের ওপারে এক সোনালী নদী বয়ে চলেছে। "
        "ঘুঘুটি নদীর রূপ দেখার জন্য ব্যাকুল হয়ে ডানা মেলল।"
    )
    bn_page1.insert_textbox(
        fitz.Rect(60, 110, 520, 400),
        bn_text_p1,
        fontname="Nirmala",
        fontsize=13,
        lineheight=1.6,
    )

    bn_page2 = bn_doc.new_page()
    bn_page2.insert_font(fontname="Nirmala", fontfile=nirmala_font_path)
    bn_text_p2 = (
        "উড়তে উড়তে সে এক মায়াবী উপত্যকায় পৌঁছাল। "
        "সেখানে সত্যিই রোদের আলোয় জলরাশি সোনার মতো জ্বলজ্বল করছিল! "
        "নদীর কলকল ধ্বনি শুনে ঘুঘুটির মন খুশিতে ভরে উঠল। "
        "সে নদীর তীরে বসে আনন্দভরে গান ধরল।"
    )
    bn_page2.insert_textbox(
        fitz.Rect(60, 80, 520, 400),
        bn_text_p2,
        fontname="Nirmala",
        fontsize=13,
        lineheight=1.6,
    )

    bn_path = samples_dir / "bangla_story_blue_dove.pdf"
    bn_doc.save(str(bn_path))
    bn_doc.close()
    print(f"Created: {bn_path}")


if __name__ == "__main__":
    generate_sample_books()
